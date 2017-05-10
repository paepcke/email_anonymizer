'''
Created on May 10, 2017

@author: paepcke
'''

import time

from email_anon.relay_server import EmailAnonServer
import util


class RelayTestBench(object):
    '''
    classdocs
    '''


    def __init__(self):
        '''
        Constructor
        '''
        self.email_checker = util.EmailChecker()
        
    def probe_clean_subject_line(self, subject_text):
        new_subject = self.email_checker.cleanSubjectOfSpamNotice(subject_text)
        print(new_subject)
    
if __name__ == '__main__':
    
    check_interval = 3
    relay =  EmailAnonServer(check_interval)
    bench = RelayTestBench()
    #bench.probe_clean_subject_line(".::MOOC Enhancement Experiment::.")
    
    relay.start()
    stop = False
    while not stop:
        time.sleep(4)
        
    relay.stop_email_check()
    
    