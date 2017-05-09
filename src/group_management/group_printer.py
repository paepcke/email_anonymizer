#!/usr/bin/env python
'''
Created on May 8, 2017

@author: paepcke
'''
import argparse
from collections import OrderedDict
import os
import sys


class GroupPrinter(object):
    '''
     Given a list of participant-groupName pairs, and a group
     ID, output the participation IDs of only the given group.
     If no participant group is provided, prints assignments
     from a previuously made assignment.
    '''

    def __init__(self, participant_source):
            
        # If participant_source is a list of participant_id/group_id
        # lists, then build the assignment dict from it:
        if type(participant_source) == list:
            self.assignments = self.make_dict_from_tuples(participant_source)
        else:
            # participant_source must be file path to an
            # assignment. Each line must be:
            #     participant_id,group_id
            with open(participant_source, 'r') as fd:
                all_assignments = fd.read().split('\n')
            # Trailing or leading newlines lead to empty 
            # elements in the list; remove those:
            try:
                while True:
                    all_assignments.remove('')
            except:
                pass
            # Now have [['<part_id1>,<group_id1>'],
            #           ['<part_id2>,<group_id2>']
            #          ]
            as_tuples = []
            for line in all_assignments:
                as_tuples.append(line.split(','))
            self.assignments = self.make_dict_from_tuples(as_tuples)

    def print_assignments(self, only_group='All'):
        '''
        Print assignments to stdout as a comma-separated list.
        If self.only_group contains the name of a group, only
        members of that group are printed, without the group.
        Thus, output is either:
           p1,g1
           p2,g1
           p3,g2
           ...
           
        Or
           p1
           p2
           p3
         where p_n are all members of the given group.
        '''
        for group in self.assignments.keys():
            if only_group != 'All' and group != only_group:
                continue
            for participant in self.assignments[group]:
                if only_group == 'All':
                    # For 'print all,' print group with each
                    # participant.
                    print('%s,%s' % (participant,group))
                else:
                    # Print only one group: only print the 
                    # participant ID:
                    print('%s' % participant)
                    
    #------------------- Utilities --------------
            
    def make_dict_from_tuples(self, participant_group_tuples):
        '''
        From:
           [['p1', 'group1'], ['p2', 'group1'], ['p3', 'group2']]
        create:
           {'group1' : ['p1', 'p2'],
            'group2' : ['p3']
            }
        
        @param participant_group_tuples: list of participant_id/group_id lists
        @type participant_group_tuples: [[string,string]]
        @return: dictionary of group-->members
        @rtype: {string : [string]}
        '''
        assignments = OrderedDict()
        for (participant_name, participant_id, group_id) in participant_group_tuples: # @UnusedVariable
            try:
                assignments[group_id].append(participant_id)
            except KeyError:
                assignments[group_id] = [participant_id]
            
        return assignments
                
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-g', '--group',
                        dest='only_group',
                        default='All',
                        help='Only output the given group'
                        )
    parser.add_argument('participant_source',
                        help='File with list of participant identfiers, such as email address,' +\
                        'or list of participant/group lists.'
                        )

    args = parser.parse_args();

    participant_source = args.participant_source
    try:
        if type(participant_source) == str:
            # Test file availability
            with open(participant_source, 'r') as fd:
                pass
    except IOError:
        print('First argument must be a readable file with participant assignments groups.')
        sys.exit(1)

    GroupPrinter(participant_source).print_assignments(args.only_group)
