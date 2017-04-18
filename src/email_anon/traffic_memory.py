'''
Created on Apr 17, 2017

@author: paepcke
'''
from shelve import DbfilenameShelf

class TrafficMemory(DbfilenameShelf):
    '''
    Persistent, write-through dictionary.
    Based on DbfilenameShelf. All writes
    and deletes immediately update the 
    disk. Not good for fast traffic or
    large dicts.
    
    Usage: TrafficMemory(<filename>) 
    '''
    def __init__(self, filename):
        DbfilenameShelf.__init__(self, filename)
        self.filename = filename

    def __setitem__(self, key, value):
        DbfilenameShelf.__setitem__(self, key, value)
        self.sync_now()
        
    def __delitem__(self, key):
        DbfilenameShelf.__delitem__(self, key)
        self.sync_now()
        
    def sync_now(self):
        filename = self.filename
        self.close()
        DbfilenameShelf.__init__(self, filename)
