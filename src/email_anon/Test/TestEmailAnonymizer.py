'''
Created on Apr 13, 2017

@author: paepcke
'''
import os
import unittest

from src.email_anon.relay_server import EmailAnonServer
from ..util import TA_NAME_MALE, TA_EMAIL_MALE, TA_SIG_MALE, \
                   TA_NAME_FEMALE, TA_EMAIL_FEMALE, TA_SIG_FEMALE, \
                   ROBO_NAME, ROBO_EMAIL, ROBO_SIG, \
                   MAILBOX_EMAIL
from src.email_anon import util


# from src.email_anon.util import TRUE_TA_EMAIL
TEST_ALL = True
#TEST_ALL = False

class TestEmailAnonymizer(unittest.TestCase):
    
    # Instance of EmailChecker available
    # to all tests. Note: the checker won't
    # be active, i.e. it won't be checking
    # emails during the test.
    
    server  = None
    checker = None
    
    @classmethod
    def setUpClass(cls):
        
        # Get one instance of the EmailAnonServer 
        # class to get access to its instance
        # variables.

        TestEmailAnonymizer.server  = EmailAnonServer()
        TestEmailAnonymizer.checker = TestEmailAnonymizer.server.email_checker
        
        # Don't need to have the 
        # email checking the imap 
        # box during testing:
        
        TestEmailAnonymizer.server.stop_email_check()
        
        # Some lists to unittest though:
        TestEmailAnonymizer.ta_names  = [TA_NAME_MALE, TA_NAME_FEMALE, ROBO_NAME] 
        TestEmailAnonymizer.ta_emails = [TA_EMAIL_MALE, TA_EMAIL_FEMALE, ROBO_EMAIL]
        TestEmailAnonymizer.ta_sigs   = [TA_SIG_MALE, TA_SIG_FEMALE, ROBO_SIG, 
                                         TA_SIG_MALE + '.', TA_SIG_FEMALE + '    ',
                                         ROBO_SIG + '\n', 
                                         TA_NAME_FEMALE, TA_NAME_FEMALE + '.', 
                                         TA_NAME_MALE + '\n', ROBO_NAME + '.   \n']
        
        
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.checker     = TestEmailAnonymizer.checker
        self.ta_names    = TestEmailAnonymizer.ta_names
        self.ta_emails   = TestEmailAnonymizer.ta_emails
        self.ta_sigs     = TestEmailAnonymizer.ta_sigs
        self.email_obscuration = self.checker.email_obscuration

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testSignatureRemoval(self):

        for sig in self.ta_sigs:         
            email_body = 'I am here\r\n%s\nHere is the rest' % sig
            new_body   = self.checker.remove_sig_if_exists(email_body)
            expected   = 'I am here\r\n\nHere is the rest'
            self.assertEqual(new_body, expected, "Failed to remove '%s'" % sig)

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testGreetingRemoval(self):

        for ta_name in self.ta_names:         
            email_body = 'Dear %s,\nNext line.' % ta_name
            new_body   = self.checker.remove_greeting_if_exists(email_body)
            expected   = 'Next line.'
            self.assertEqual(new_body, expected, "Failed to remove '%s'" % ta_name)

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testThreadEmailRemoval(self):
    
        # In a long email thread, test replacement of 
        # the email address in the thread section headers, such as:
        #   On 2017-09-30 <roboTA@cs.stanford.edu> wrote:
        #     Old msg.
        # with:
        #   On 2017-09-30 <***obscured***> wrote:
        #     Old msg.
 
        email_body = 'First line\nsecond line.\n%s' %\
            'On 2017-09-30 <roboTA@cs.stanford.edu> wrote:\nOld msg.'
        new_body   = self.checker.obscure_thread_headers(email_body)
        expected   = 'First line\nsecond line.\n%s' %\
            ('On 2017-09-30 %s wrote:\nOld msg.' % self.email_obscuration)
        self.assertEqual(new_body, expected, "Failed to obscure single thread header in '%s'" % email_body)
        
        # Now two thread headers:
        email_body = 'First line\nsecond line.\n%s' %\
            'On 2017-09-30 <roboTA@cs.stanford.edu> wrote:\nOld msg.' +\
            'Third line\n%s' %\
            '>> On 2017-09-30 <roboTA@cs.stanford.edu> wrote:\nEven older msg.'
        new_body = self.checker.obscure_thread_headers(email_body)
        
        expected = 'First line\nsecond line.\n%s' %\
            'On 2017-09-30 %s wrote:\nOld msg.' % self.email_obscuration +\
            'Third line\n%s' %\
            '>> On 2017-09-30 %s wrote:\nEven older msg.' % self.email_obscuration 

        self.assertEqual(new_body, expected, "Failed to obscure multi-thread header in '%s'" % email_body)
        

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testThreadEmailRecovery(self):
        
        # Test recovering the obscured email addresses
        # in thread headers. See testThreadEmailRecovery()
        # for details
        
        email_body = 'First line\nsecond line.\n%s' %\
            'On 2017-09-30 %s wrote:\nOld msg.' % self.email_obscuration
        new_body   = self.checker.recover_thread_headers(email_body, ROBO_EMAIL)
        expected   = 'First line\nsecond line.\n%s' %\
            'On 2017-09-30 <%s> wrote:\nOld msg.' % ROBO_EMAIL
        self.assertEqual(new_body, expected, "Failed to replace thread email in '%s'" % email_body)
        
        # Now more than one previously obscured thread header:
        second_email_body = 'First line\nsecond line.\n%s' %\
            'On 2017-09-30 %s wrote:\nOld msg.' % self.email_obscuration +\
            'Third line\n%s' %\
            '>> On 2017-09-30 %s wrote:\nEven older msg.' % self.email_obscuration  
        new_body   = self.checker.recover_thread_headers(second_email_body, ROBO_EMAIL)
        expected   = 'First line\nsecond line.\n%s' %\
            'On 2017-09-30 <roboTA@cs.stanford.edu> wrote:\nOld msg.' +\
            'Third line\n%s' %\
            '>> On 2017-09-30 <roboTA@cs.stanford.edu> wrote:\nEven older msg.'
        self.assertEqual(new_body, expected, "Failed to recover thread email in '%s'" % second_email_body)

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testRemoveSubjectSpamNotice(self):
        
        subject       = '*****SPAM***** Fw: Reminder: update required due to payment issue'
        new_subject   = self.checker.cleanSubjectOfSpamNotice(subject)
        expected      = 'Fw: Reminder: update required due to payment issue'
        self.assertEqual(new_subject, expected, "Failed to replace thread email in '%s'" % new_subject)


    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testNoGuessMsgToTa(self):
        
        subject = 'Testing non-guess RouteNo:<CAFKHkni2H3CUmehRLppk3+Ym_zsib2hDkBBJM+c2VVdkzpKoiQ@mail.gmail.com>'
        body    = 'Jumping the gun without\na guess here.'
        new_body = self.checker.admin_msg_to_ta_with_return(subject, 
                                                            body,
                                                            msg_to_ta='Forgot the guess.',
                                                            testing=True) # prevent actual sending
        
        
        expected = 'Message from relay: Forgot the guess.<br>' +\
                   '<a href="mailto:%s' % MAILBOX_EMAIL +\
                   '?subject=Testing non-guess RouteNo:<CAFKHkni2H3CUmehRLppk3+Ym_zsib2hDkBBJM+c2VVdkzpKoiQ@mail.gmail.com>' +\
                   '&body=Jumping%20the%20gun%20without%0Aa%20guess%20here.">' +\
                   'Click here to fix and resend.</a>'

        self.assertEqual(new_body, expected, 'Did not parse or react to missing guess correctly.')

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testGuessDetectionAndRemoval(self):
        subject 	= 'Test subject'
        body    	= 'Body without a guess.'
        date    	= '2017-10-3'
        msg_id  	= 'TestMsg'
        true_origin = ROBO_EMAIL
        new_body = self.checker.register_ta_guess(subject, body, date, msg_id, true_origin, testing=True)
        # Since there is no guess in the body we created above,
        # expect None as response:
        self.assertIsNone(new_body, 'Did not detect absence of signature.')
        
        # Now one that does have a sig:
        body = 'H\nThis has a guess.'
        new_body = self.checker.register_ta_guess(subject, body, date, msg_id, true_origin, testing=True)
        expected = 'This has a guess.'
        self.assertEqual(new_body, expected, 'Did not properly remove signature.')

    @unittest.skipIf(not TEST_ALL, "Temporarily disabled")    
    def testGuessPersistification(self):
        
        # Use a different file for testing the record
        # keeping than the true ops file:
        guess_file = 'guess_test.csv'
        util.GUESS_RECORD_FILE = guess_file
        guess_file_path = os.path.join('..', guess_file)
        if not os.path.exists(guess_file_path):
            os.remove('../%s' % guess_file_path)
        
        date = '2017-10-4'
        msg_id = 'TstMsgId'
        # Used to tell how many lines to read
        # from the result file: 
        for true_origin in [TA_EMAIL_FEMALE, TA_EMAIL_MALE, ROBO_EMAIL]:
            for raw_guess in ['human','h','Human','H','robot','r','Robot','R']:
                self.checker.persist_ta_guess(date, msg_id, true_origin, raw_guess)
                truth = 'human' if true_origin == TA_EMAIL_FEMALE or true_origin == TA_EMAIL_MALE else 'robot'
                guess = 'human' if raw_guess in ['h','H','human','Human'] else 'robot'

                with open(guess_file_path, 'r') as fd:
                    # Read the column header:
                    col_names = fd.readline().strip()
                    true_col_names = 'date,msg_id,true_origin,guessed_origin'
                    self.assertEqual(col_names, true_col_names, 'Column names not correct in guess file.')
                    # Read all the lines:
                    all_guess_records = fd.readlines()
                    guess_record = all_guess_records[-1].strip()
                    
                expected = '%s,%s,%s,%s' % (date, msg_id, truth, guess.lower())
                self.assertEqual(guess_record, expected, "Incorrect record for guess: Expected '%s' BUT got '%s'" %\
                                 (expected, guess_record))

        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()