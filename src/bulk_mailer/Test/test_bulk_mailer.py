'''
Created on Apr 18, 2017

@author: paepcke
'''

# TODO:
# Test resumption
  
import os
import time
import unittest

from bulk_mailer.bulk_mailer import BulkMailer


TEST_ALL = True
#TEST_ALL = False


class TestBulkMailer(unittest.TestCase):

    script_dir        = os.path.dirname(__file__)
    email_body_file   = os.path.join(script_dir,'email_body_testfile.txt')
    email_addr_file   = os.path.join(script_dir,'email_addr_testfile.txt')
    batch_size        = 2
    inter_msg_delay   = 1     # seconds
    inter_batch_delay = 2/60. # minutes (2 seconds)
    
    # All email addresses in the test file
    

    def setUp(self):
        self.mailer = BulkMailer(TestBulkMailer.email_body_file,
                                 TestBulkMailer.email_addr_file, 
                                 batch_size=TestBulkMailer.batch_size,
                                 inter_msg_delay=TestBulkMailer.inter_msg_delay,      # seconds
                                 inter_batch_delay=TestBulkMailer.inter_batch_delay,  # minutes
                                 unit_test_case_obj=self
                 )
        # Array of email addresses sent. 
        # Appended to by the sending() callback:
        self.email_addrs_sent = []
        self.all_email_addrs   = []
        
        # No resume info at the outset:
        try:
            os.remove(self.mailer.resume_place_file)
        except OSError:
            pass
        
        with open(TestBulkMailer.email_addr_file, 'r') as fd:
            addr = self.mailer.next_addr(fd)
            while addr is not None:
                self.all_email_addrs.append(addr)
                addr = self.mailer.next_addr(fd)

    def tearDown(self):
        self.mailer.shutdown()

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")
    def testIsolateEmailAddr(self):
        
        test_addr = 'bluebell@my.company.com'
        line = test_addr
        addr = self.mailer.isolate_email_addr(line)
        self.assertEqual(addr, test_addr, 'Email-only line failed.')
        
        line = '     %s' % test_addr
        addr = self.mailer.isolate_email_addr(line)
        self.assertEqual(addr, test_addr, 'Email leading blanks failed.')
        
        line = '%s and garbage' % test_addr
        addr = self.mailer.isolate_email_addr(line)
        self.assertEqual(addr, test_addr, 'Email plus space plus garbage failed.')
        
        line = '%s,and garbage' % test_addr
        addr = self.mailer.isolate_email_addr(line)
        self.assertEqual(addr, test_addr, 'Email plus comma plus garbage failed.')

        line = '%s,    and garbage' % test_addr
        addr = self.mailer.isolate_email_addr(line)
        self.assertEqual(addr, test_addr, 'Email plus comma plus space plus garbage failed.')
        
        line = '# %s and garbage' % test_addr
        addr = self.mailer.isolate_email_addr(line)
        self.assertIsNone(addr, 'Comment line.')

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")
    def testNextAddr(self):
        
        emails_read = 0 #@UnusedVariable
        with open(TestBulkMailer.email_addr_file, 'r') as fd:
            next_addr = self.mailer.next_addr(fd)
            self.assertEqual(next_addr, 'fritz@fake.com', 'Failed initial email')
            
            # Skip over susie:
            self.mailer.next_addr(fd)
            # Make sure the empty line to the next batch
            # is understood:
            next_addr = self.mailer.next_addr(fd)
            self.assertEqual(next_addr, 'fritz@fake.com', 'Failed second-batch email')
            
            # We just read three emails:
            emails_read = 3

            # Get the remaining emails, and count them:
            while next_addr is not None:
                next_addr = self.mailer.next_addr(fd)
                if next_addr is not None:
                    emails_read +=1

        self.assertEqual(emails_read, len(self.all_email_addrs), 'Independent num-of-emails count mismatch.')

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")
    def testSendingAll(self):
        '''
        Mailer is exercised, including delays. But
        no mail is actually sent.
        '''
        
        num_msgs    = len(self.all_email_addrs)
        num_batches = num_msgs / 2  # Each batch has 2 msgs
        
        # Elapsed time should be (comes to ~11 sec for 12
        # email addrs in the test file:
        expected_time = self.inter_msg_delay * (num_msgs - num_batches) +\
                        60 * self.inter_batch_delay * (num_batches - 1)
        print("Test sending %s emails with pauses; takes about %s seconds" %
              (num_msgs, expected_time))
        
        start_time = time.time()
        self.mailer.start()
        self.mailer.join()
        elapsed_time   = time.time() - start_time

        # Correct number of messages should have been sent:
        self.assertEqual(self.all_email_addrs, self.email_addrs_sent)
        
        # Time for sending all should be as expected:
        self.assertAlmostEqual(elapsed_time, expected_time, delta=1, msg="Elapsed: %s; Expected: %s" %\
                                (elapsed_time,expected_time))                

    
    #------------------- Utilities ------------------
    
    def sending(self, email_addr):
        self.email_addrs_sent.append(email_addr)            

        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()