from django.core.management.base import BaseCommand, CommandError
from polls.models import Poll

class Command(BaseCommand):
  help = 'Closes the specified poll for voting'

  def add_arguments(self, parser):
    parser.add_argument('directory', type=string)

    # Named (optional) arguments
    parser.add_argument('--root_directory',
      dest='root_dir',
      help="""Specifies the root of all images directory, in case it is modified on the server. Images are 
           identified by their relative path name to this root.""")

  def handle(self, *args, **options):
    
    current_directory = options['directory']
      
    if options['root_directory']:
      root_dir = options['root_directory']
    
    
      try:
        poll = Poll.objects.get(pk=poll_id)
      except Poll.DoesNotExist:
        raise CommandError('Poll "%s" does not exist' % poll_id)
  
    poll.opened = False
    poll.save()
  
    self.stdout.write('Successfully closed poll "%s"' % poll_id)