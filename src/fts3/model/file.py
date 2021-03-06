from sqlalchemy import Column, DateTime, Float
from sqlalchemy import ForeignKey, Integer, String

from base import Base, Json

FileActiveStates = ['SUBMITTED', 'READY', 'ACTIVE', 'STAGING']

class File(Base):
	__tablename__ = 't_file'
	
	file_id      	     = Column(Integer, primary_key = True)
	file_index           = Column(Integer)
	job_id         	     = Column(String(36), ForeignKey('t_job.job_id'))
	source_se            = Column(String(255))
	dest_se              = Column(String(255))
	symbolicname 	     = Column(String(255))
	file_state   	     = Column(String(32))
	transferhost 	     = Column(String(255))
	source_surl          = Column(String(1100))
	dest_surl            = Column(String(1100))
	agent_dn             = Column(String(1024))
	error_scope          = Column(String(32))
	error_phase          = Column(String(32))
	reason_class         = Column(String(32))
	reason               = Column(String(2048))
	num_failures         = Column(Integer)
	current_failures     = Column(Integer)
	filesize             = Column(Float)
	checksum             = Column(String(100))
	finish_time          = Column(DateTime)
	start_time           = Column(DateTime)
	internal_file_params = Column(String(255))
	job_finished         = Column(DateTime)
	pid          	     = Column(Integer)
	tx_duration  	     = Column(Float)
	throughput   	     = Column(Float)
	retry       	     = Column(Integer)
	user_filesize        = Column(Float)
	file_metadata        = Column(Json(255))
	staging_start        = Column(DateTime)
	staging_finished     = Column(DateTime)
	selection_strategy   = Column(String(255))
	bringonline_token    = Column(String(255))
	
	def isFinished(self):
		return self.job_state not in FileActiveStates
	
	def __str__(self):
		return str(self.file_id)
