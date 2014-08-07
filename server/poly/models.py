from django.db import models

# Polygon models are in the 'shapes' app

# This django app currently just supplies coffeescript files for editing and
# viewing polygon segmentations

from common.models import UserBase, ResultBase
from common.utils import compute_label_reward, md5sum

class Picture(models.Model):
  
  file = models.ImageField(upload_to='pictures', storage=STORAGE)
  name = models.TextField(blank=False)
  
  #: hash for simple duplicate detection
  md5 = models.CharField(max_length=32)  

  def get_entry_dict(self):
    """ Return a dictionary of this model containing just the fields needed
    for javascript rendering.  """

    return {
        'id': self.id,
    }

  
  def save(self, *args, **kwargs):
    if not self.md5:
      self.md5 = md5sum(self.image_orig)
    
    super(Picture, self).save(*args, **kwargs)


class PolygonResults(ResultBase):
  """Class for storing the segmentation results from users"""

  picture = models.ForeignKey(Picture)

  #: Vertices format: x1,y1,x2,y2,x3,y3,... (coords are fractions of width/height)
  #: (this format allows easy embedding into javascript)
  vertices = models.TextField()
  #: num_vertices should be equal to len(points.split(','))//2
  num_vertices = models.IntegerField(db_index=True)

  #: Triangles format: p1,p2,p3,p2,p3,p4..., where p_i is an index into
  #: vertices, and p1-p2-p3 is a triangle.  Each triangle is three indices
  #: into points; all triangles are listed together.  This format allows easy
  #: embedding into javascript.
  triangles = models.TextField()
  #: num_triangles should be equal to len(triangles.split(','))//3
  num_triangles = models.IntegerField()

  #: Segments format: "p1,p2,p2,p3,...", where p_i is an index into vertices,
  #: and p1-p2, p2-p3, ... are the line segments.  The segments are unordered.
  #: Each line segment is two indices into points; all segments are listed
  #: together.  This format allows easy embedding into javascript.
  segments = models.TextField()
  #: num_segments should be equal to len(segments.split(','))//2
  num_segments = models.IntegerField()


  # Raffi: I think this is used for generating views of the current segmentation
  def segments_svg_path(self):
      """ Returns all line segments as SVG path data """
      verts = self.vertices.split(',')  # leave as string
      segs = [int(v) for v in self.segments.split(',')]
      data = []
      for i in xrange(0, len(segs), 2):
          v0 = 2 * segs[i]
          v1 = 2 * segs[i + 1]
          data.append(u"M%s,%sL%s,%s" % (
              verts[v0], verts[v0 + 1],
              verts[v1], verts[v1 + 1],
          ))
      return u"".join(data)  

  def get_entry_dict(self):
    """ Return a dictionary of this model containing just the fields needed
    for javascript rendering.  """

    # generating thumbnail URLs is slow, so only generate the ones
    # that will definitely be used.
    ret = {
        'id': self.id,
        'vertices': self.vertices,
        'segments': self.segments,
        'picture': self.picture.get_entry_dict(),
    }
    return ret


  def save(self, *args, **kwargs):
    if not self.reward:
      self.reward = compute_label_reward(self)

    if not self.num_vertices:
      self.num_vertices = len(self.vertices.split(',')) // 2

    if not self.num_segments:
      self.num_segments = len(self.segments.split(',')) // 2
    
    
    super(PolygonResults, self).save(*args, **kwargs)

  class Meta:
    abstract = True
    ordering = ['picture', '-name']

  
  @staticmethod
  def mturk_submit(user, 
                   hit_contents, 
                   results, 
                   time_ms, 
                   time_active_ms, 
                   version,
                   mturk_assignment=None, 
                   **kwargs):

    """ Add new instances from a mturk HIT after the user clicks [submit] """

    if unicode(version) != u'1.0':
        raise ValueError("Unknown version: %s" % version)

    photo = hit_contents[0]
    poly_list = results[str(photo.id)]
    time_ms_list = time_ms[str(photo.id)]
    time_active_ms_list = time_active_ms[str(photo.id)]

    if len(poly_list) != len(time_ms_list):
        raise ValueError("Result length mismatch (%s polygons, %s times)" % (
            len(poly_list), len(time_ms_list)))

    shape_model = MaterialShape
    slug = experiment.slug
    if slug == "segment_material":
        shape_type = 'M'
    elif slug == "segment_object":
        shape_type = 'O'
    else:
        raise ValueError("Unknown slug: %s" % slug)

    # store results in SubmittedShape objects
    new_objects_list = []
    for idx in xrange(len(poly_list)):
        poly_vertices = poly_list[idx]
        poly_time_ms = time_ms_list[idx]
        poly_time_active_ms = time_active_ms_list[idx]

        num_vertices = len(poly_vertices)
        if num_vertices % 2 != 0:
            raise ValueError("Odd number of vertices (%d)" % num_vertices)
        num_vertices //= 2

        new_obj, created = photo.submitted_shapes.get_or_create(
            user=user,
            mturk_assignment=mturk_assignment,
            time_ms=poly_time_ms,
            time_active_ms=poly_time_active_ms,
            # (repr gives more float digits)
            vertices=','.join([repr(f) for f in poly_vertices]),
            num_vertices=num_vertices,
            shape_type=shape_type
        )

        if created:
            new_objects_list.append(new_obj)

    # triangulate polygons (creates instances of shape_model)
    if new_objects_list:
        from shapes.tasks import triangulate_submitted_shapes_task
        triangulate_submitted_shapes_task.delay(
            photo, user, mturk_assignment, shape_model, new_objects_list)

    if new_objects_list:
        return {get_content_tuple(photo): new_objects_list}
    else:
        return {}

