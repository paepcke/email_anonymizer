'''
Created on May 7, 2017

@author: paepcke
'''
from StringIO import StringIO
from contextlib import contextmanager
import sys
import tempfile
import unittest
from unittest.case import skipIf

from group_management.group_assigner import GroupAssigner


#*****testAll = True
testAll = False

DO_RANDOMIZE = True

class TestGroupAssigner(unittest.TestCase):


    def setUp(self):
        self.participant_ids = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8']
        self.group_ids       = ['group1', 'group2', 'group3']

    def tearDown(self):
        pass

    @skipIf(not testAll, 'Temporarily disabled')
    def testFewerMembersThanGroups(self):
        participants = self.participant_ids[0:2]
        assignments = GroupAssigner(participants, self.group_ids, DO_RANDOMIZE).assign()
        expected    = {'group1': ['p1'],
                       'group2': ['p2'],
                       'group3': []
                      }
        self.assertDictEquivalent(expected, assignments, participants)

    @skipIf(not testAll, 'Temporarily disabled')
    def testSameNumMembersAsGroups(self):
        participants = self.participant_ids[0:3]
        assignments = GroupAssigner(participants, self.group_ids, DO_RANDOMIZE).assign()
        expected    = {'group1': ['p1'],
                       'group2': ['p2'],
                       'group3': ['p3']
                      }
        self.assertDictEquivalent(expected, assignments, participants)
    
    @skipIf(not testAll, 'Temporarily disabled')
    def testNoRemainder(self):
        participants = self.participant_ids[0:6]
        assignments = GroupAssigner(participants, self.group_ids, DO_RANDOMIZE).assign()
        expected    = {'group1': ['p1', 'p2'],
                       'group2': ['p3', 'p4'],
                       'group3': ['p5', 'p6']
                      }
        self.assertDictEquivalent(expected, assignments, participants)
        
    @skipIf(not testAll, 'Temporarily disabled')
    def testWithRemainder(self):
        participants = self.participant_ids
        assignments = GroupAssigner(participants, self.group_ids, DO_RANDOMIZE).assign()
        expected    = {'group1': ['p1', 'p2', 'p7'],
                       'group2': ['p3', 'p4', 'p8'],
                       'group3': ['p5', 'p6']
                      }
        self.assertDictEquivalent(expected, assignments, participants)
        
    @skipIf(not testAll, 'Temporarily disabled')
    def testParticipantsFromFile(self):
        participants = self.participant_ids
        try:
            participant_file_fd = tempfile.NamedTemporaryFile(dir='/tmp')
            participant_file_fd.write('\n'.join(str(participant_id) for participant_id in participants))
            participant_file_fd.write('\n')
            participant_file_fd.flush()
            
            assignments = GroupAssigner(participant_file_fd.name, self.group_ids, DO_RANDOMIZE).assign()
            expected    = {'group1': ['p1', 'p2', 'p7'],
                           'group2': ['p3', 'p4', 'p8'],
                           'group3': ['p5', 'p6']
                          }
            self.assertDictEquivalent(expected, assignments, participants)
        finally: 
            participant_file_fd.close()
        
    @skipIf(not testAll, 'Temporarily disabled')
    def testCreateDictFromTuples(self):
        '''
        Given an array of tuples, is a proper
        assignment dict constructed?
        '''
        input_assignments = [('p1', 'group1'), ('p2', 'group1'),('p7', 'group1'),
                             ('p3', 'group2'), ('p4', 'group2'),('p8', 'group2'),
                             ('p5', 'group3'), ('p6', 'group3')
                             ]
        assignments = GroupAssigner(input_assignments, 
                                    ['group1'],  # group IDs 
                                    False,       # randomize is irrelevant
                                    only_group='All' 
                                    ).build_dict_from_tuples(input_assignments)
        expected    = {'group1': ['p1', 'p2', 'p7'],
                       'group2': ['p3', 'p4', 'p8'],
                       'group3': ['p5', 'p6']
                      }
        self.assertDictEquivalent(expected, assignments, self.participant_ids)

    @skipIf(not testAll, 'Temporarily disabled')
    def testPrintOnlyOneGroup(self):
        
        input_assignments = [('p1', 'group1'), ('p2', 'group1'),('p7', 'group1'),
                             ('p3', 'group2'), ('p4', 'group2'),('p8', 'group2'),
                             ('p5', 'group3'), ('p6', 'group3')
                             ]
        grouper = GroupAssigner(input_assignments, 
                                ['group1', 'group2', 'group3'],  # group IDs 
                                False,       # randomize is irrelevant
                                only_group='group1' 
                                )
        
        expected = ['p1', 'p2', 'p7']
        with self.captured_output() as (out, err): # @UnusedVariable
            grouper.run()
            
        # This can go inside or outside the `with` block
        output = out.getvalue().strip()
        self.assertEqual(output, expected)
           
    # ----------- Utilities ----------------------

    def assertDictEquivalent(self, dict1, dict2, reference_list):
        '''
        Given two dicts, ensure that they have the same
        keys, that all values are lists, and that the
        concatenation of those lists is a permutation of
        the given reference list. Raisses assertion exception
        if violation. 
        '''
        
        keys1 = dict1.keys()
        keys2 = dict2.keys()
        try:
            for key in keys1:
                # Remove from keys2 in place
                keys2.remove(key)
        except ValueError:
            raise AssertionError("Dicts don't have the same keys")
        
        list_union_dict1 = []
        for key_dict1 in dict1.keys():
            list_union_dict1.extend(dict1[key_dict1])
            
        list_union_dict2 = []
        for key_dict2 in dict2.keys():
            list_union_dict2.extend(dict2[key_dict2])

        # The lists turned to sets should be set-equal:
        self.assertSetEqual(set(list_union_dict1), set(list_union_dict2), "Dict1 values: %s, Dict2 values: %s" % (list_union_dict1, list_union_dict2))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testFewerMembersThanGroups']
    unittest.main()