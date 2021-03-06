"""Routes configuration

The more specific and detailed routes should be defined first so they
may take precedent over the more generic routes. For more information
refer to the routes manual at http://routes.groovie.org/docs/
"""
from routes import Mapper

def make_map(config):
	"""Create, configure and return the routes Mapper"""
	map = Mapper(directory=config['pylons.paths']['controllers'],
	             always_scan=config['debug'])
	map.minimization = False
	map.explicit = False
	
	# The ErrorController route (handles 404/500 error pages); it should
	# likely stay at the top, ensuring it can always be resolved
	map.connect('/error/{action}', controller='error')
	map.connect('/error/{action}/{id}', controller='error')
	
	# Root
	map.connect('/', controller='misc', action='apiVersion')
	
	# Whoami
	map.connect('/whoami', controller='misc', action='whoami')
	
	# Delegation
	map.connect('/delegation/{id}', controller='delegation', action='view')
	map.connect('/delegation/{id}/{action}', controller='delegation')
	
	# Jobs
	map.connect('/jobs', controller='jobs', action='index',
				conditions = dict(method = ['GET']))
	map.connect('/jobs/', controller='jobs', action='index',
				conditions = dict(method = ['GET']))
	map.connect('/jobs/{id}', controller='jobs', action='show',
				conditions = dict(method = ['GET']))
	map.connect('/jobs/{id}/{field}', controller='jobs', action='showField',
				conditions = dict(method = ['GET']))
	map.connect('/jobs/{id}', controller='jobs', action='cancel',
				conditions = dict(method = ['DELETE']))
	map.connect('/jobs', controller='jobs', action='submit',
			    conditions = dict(method = ['PUT', 'POST']))
	
	# Schema definition
	map.connect('/schema/{action}', controller='schema')
	
	# Configuration audit
	map.connect('/config/audit', controller='config', action='audit')

	return map
