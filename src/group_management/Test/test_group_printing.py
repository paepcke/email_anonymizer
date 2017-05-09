'''
Created on May 8, 2017

@author: paepcke
'''
from StringIO import StringIO
from contextlib import contextmanager
import sys
import unittest
from unittest.case import skipIf

from group_management.group_printer import GroupPrinter

testAll = True
#testAll = False

class TestGroupPrinting(unittest.TestCase):

    def setUp(self):
        self.participant_ids = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8']
        self.group_ids       = ['group1', 'group2', 'group3']

    @skipIf(not testAll, 'Temporarily disabled')
    def testPrintOnlyOneGroup(self):
        
        input_assignments = [('name1', 'p1', 'group1'), ('name2', 'p2', 'group1'),('name7', 'p7', 'group1'),
                             ('name3', 'p3', 'group2'), ('name4', 'p4', 'group2'),('name8', 'p8', 'group2'),
                             ('name5', 'p5', 'group3'), ('name6', 'p6', 'group3')
                             ]
        
        printer = GroupPrinter(input_assignments)
        
        expected = 'p1\np2\np7\n'
        with self.captured_output() as (out, err): # @UnusedVariable
            printer.print_assignments('group1')
            
        # This can go inside or outside the `with` block
        output = out.getvalue()
        self.assertEqual(output, expected)

    @skipIf(not testAll, 'Temporarily disabled')
    def testPrintAllGroups(self):
        
        input_assignments = [('name1', 'p1', 'group1'), ('name2', 'p2', 'group1'),('name7', 'p7', 'group1'),
                             ('name3', 'p3', 'group2'), ('name4', 'p4', 'group2'),('name8', 'p8', 'group2'),
                             ('name5', 'p5', 'group3'), ('name6', 'p6', 'group3')
                             ]
        printer = GroupPrinter(input_assignments)
        
        
        expected ='p1,group1\n' +\
        'p2,group1\n' +\
        'p7,group1\n' +\
        'p3,group2\n' +\
        'p4,group2\n' +\
        'p8,group2\n' +\
        'p5,group3\n' +\
        'p6,group3\n'
        
        with self.captured_output() as (out, err): # @UnusedVariable
            printer.print_assignments()
            
        # This can go inside or outside the `with` block
        output = out.getvalue()
        self.assertEqual(output, expected)


    #-------------------- Utilities ----------------------
    
    @contextmanager
    def captured_output(self):
        new_out, new_err = StringIO(), StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = new_out, new_err
            yield sys.stdout, sys.stderr
        finally:
            sys.stdout, sys.stderr = old_out, old_err

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()