from datetime import datetime, timedelta
from fts3.model import Job, File, JobActiveStates
from fts3.model import Credential, BannedSE
from fts3rest.lib.base import BaseController, Session
from fts3rest.lib.helpers import jsonify
from fts3rest.lib.middleware.fts3auth import authorize, authorized
from fts3rest.lib.middleware.fts3auth.constants import *
from pylons import request
from pylons.controllers.util import abort
import json
import re
import socket
import types
import urllib
import urlparse
import uuid


DEFAULT_PARAMS = {
	'bring_online'     : -1,
	'verify_checksum'  : False,
	'copy_pin_lifetime': -1,
	'gridftp'          : '',
	'job_metadata'     : None,
	'overwrite'        : False,
	'reuse'            : False,
	'source_spacetoken': '',
	'spacetoken'       : ''
}


class JobsController(BaseController):
	
	def _getJob(self, id):
		job = Session.query(Job).get(id)
		if job is None:
			abort(404, 'No job with the id "%s" has been found' % id)
		if not authorized(TRANSFER, resource_owner = job.user_dn, resource_vo = job.vo_name):
			abort(403, 'Not enough permissions to check the job "%s"' % id)
		return job
		
	@authorize(TRANSFER)
	@jsonify
	def index(self, **kwargs):
		"""GET /jobs: All jobs in the collection"""
		jobs = Session.query(Job).filter(Job.job_state.in_(JobActiveStates))
		
		# Filtering
		if 'user_dn' in request.params and request.params['user_dn']:
			jobs = jobs.filter(Job.user_dn == request.params['user_dn'])
		if 'vo_name' in request.params and request.params['vo_name']:
			jobs = jobs.filter(Job.vo_name == request.params['vo_name'])
		
		# Return
		return jobs.all()
	
	@jsonify
	def cancel(self, id, **kwargs):
		"""DELETE /jobs/id: Delete an existing item"""
		job = self._getJob(id)
		
		if job.job_state in JobActiveStates:
			now = datetime.now()
			
			job.job_state    = 'CANCELED'
			job.finish_time  = now
			job.job_finished = now
			job.reason       = 'Job canceled by the user'
			
			for f in job.files:
				if f.file_state in JobActiveStates:
					f.file_state   = 'CANCELED'
					f.job_finished = now
					f.finish_time  = now
					f.reason       = 'Job canceled by the user'
				
			Session.merge(job)
			Session.commit()
			
			job = self._getJob(id)

		files = job.files
		return job
	
	@jsonify
	def show(self, id, **kwargs):
		"""GET /jobs/id: Show a specific item"""
		job = self._getJob(id)
		files = job.files # Trigger the query, so it is serialized
		return job
	
	@jsonify
	def showField(self, id, field, **kwargs):
		"""GET /jobs/id/field: Show a specific field from an item"""
		job = self._getJob(id)
		if hasattr(job, field):
			return getattr(job, field)
		else:
			abort(404, 'No such field')
	
	@authorize(TRANSFER)
	@jsonify
	def submit(self, **kwargs):
		"""PUT /jobs: Submits a new job"""
		# First, the request has to be valid JSON
		try:
			if request.method == 'PUT':
				unencodedBody = request.body
			elif request.method == 'POST':
				if request.content_type == 'application/json':
					unencodedBody = request.body
				else:
					unencodedBody = urllib.unquote_plus(request.body)
			else:
				abort(400, 'Unsupported method %s' % request.method)
				
			submittedDict = json.loads(unencodedBody)
						
		except ValueError, e:
			abort(400, 'Badly formatted JSON request (%s)' % str(e))

		# The auto-generated delegation id must be valid
		user = request.environ['fts3.User.Credentials']
		credential = Session.query(Credential).get((user.delegation_id, user.user_dn))
		if credential is None:
			abort(403, 'No delegation id found for "%s"' % user.user_dn)
		if credential.expired():
			remaining = credential.remaining()
			seconds = abs(remaining.seconds + remaining.days * 24 * 3600)
			abort(403, 'The delegated credentials expired %d seconds ago' % seconds)
		if credential.remaining() < timedelta(hours = 1):
			abort(403, 'The delegated credentials has less than one hour left')
		
		# Populate the job and file
		job = self._setupJobFromDict(submittedDict, user)
		
		# Set job source and dest se depending on the transfers
		self._setJobSourceAndDestination(job)
		
		# Return it
		Session.merge(job)
		Session.commit()
			
		return job

	def _setJobSourceAndDestination(self, job):
		job.source_se = job.files[0].source_se
		job.dest_se   = job.files[0].dest_se
		for file in job.files:
			if file.source_se != job.source_se:
				job.source_se = None
			if file.dest_se != job.dest_se:
				job.dest_se = None


	def _setupJobFromDict(self, serialized, user):
		try:
			if len(serialized['files']) == 0:
				abort(400, 'No transfers specified')
								
			# Initialize defaults
			# If the client is giving a NULL for a parameter with a default,
			# use the default
			params = dict()
			params.update(DEFAULT_PARAMS)
			if 'params' in serialized:
				params.update(serialized['params'])
				for (k, v) in params.iteritems():
					if v is None and k in DEFAULT_PARAMS:
						params[k] = DEFAULT_PARAMS[k]
			
			# Create
			job = Job()
			
			# Job
			job.job_id                   = str(uuid.uuid1())
			job.job_state                = 'SUBMITTED'
			job.reuse_job                = self._yesOrNo(params['reuse'])
			job.job_params               = params['gridftp']
			job.submit_host              = socket.getfqdn() 
			job.user_dn                  = user.user_dn
			
			if 'credential' in serialized:
				job.user_cred  = serialized['credential']
				job.cred_id    = str()
			else:
				job.user_cred  = str()
				job.cred_id    = user.delegation_id
			
			job.voms_cred                = ' '.join(user.voms_cred)
			job.vo_name                  = user.vos[0]
			job.submit_time              = datetime.now()
			job.priority                 = 3
			job.space_token              = params['spacetoken']
			job.overwrite_flag           = self._yesOrNo(params['overwrite'])
			job.source_space_token       = params['source_spacetoken'] 
			job.copy_pin_lifetime        = int(params['copy_pin_lifetime'])
			job.verify_checksum          = self._yesOrNo(params['verify_checksum'])
			job.bring_online             = int(params['bring_online'])
			job.job_metadata             = params['job_metadata']
			job.job_params               = str()
			
			# Files
			findex = 0
			for t in serialized['files']:
				job.files.extend(self._populateFiles(t, findex))
				findex += 1
				
			if len(job.files) == 0:
				abort(400, 'No pair with matching protocols')
				
			# If copy_pin_lifetime is specified, go to staging directly
			if job.copy_pin_lifetime > -1:
				job.job_state = 'STAGING'
				for t in job.files:
					t.file_state = 'STAGING'
				
			return job
		
		except ValueError:
			abort(400, 'Invalid value within the request')
		except TypeError, e:
			abort(400, 'Malformed request: %s' % str(e))
		except KeyError, e:
			abort(400, 'Missing parameter: %s' % str(e))


	def _protocolMatchAndValid(self, src, dst):
		forbiddenSchemes = ['', 'file']
		return src.scheme not in forbiddenSchemes and\
				dst.scheme not in forbiddenSchemes and\
				(src.scheme == dst.scheme or src.scheme == 'srm' or dst.scheme == 'srm') 


	def _populateFiles(self, serialized, findex):
		files = []
		
		# Extract matching pairs
		pairs = []
		for s in serialized['sources']:
			for d in serialized['destinations']:
				source_url = urlparse.urlparse(s)
				dest_url   = urlparse.urlparse(d)
				if self._protocolMatchAndValid(source_url, dest_url):
					pairs.append((s, d))
					
		# Create one File entry per matching pair
		for (s, d) in pairs:
			file = File()
			
			file.file_index  = findex
			file.file_state  = 'SUBMITTED'
			file.source_surl = s
			file.dest_surl   = d
			file.source_se   = self._getSE(s)
			file.dest_se     = self._getSE(d)
			
			file.user_filesize = serialized.get('filesize', None)
			file.selection_strategy = serialized.get('selection_strategy', None)
			
			if 'checksum' in serialized:
				file.checksum = str(serialized['checksum'])
			
			if 'metadata' in serialized:
				file.file_metadata = serialized['metadata']
			
			files.append(file)
		
		return files
	
			
	def _getSE(self, uri):
		parsed = urlparse.urlparse(uri)
		return "%s://%s" % (parsed.scheme, parsed.hostname)

	
	
	def _yesOrNo(self, value):
		if type(value) is types.StringType:
			return len(value) > 0 and value[0].upper() == 'Y'
		elif value:
			return True
		else:
			return False
