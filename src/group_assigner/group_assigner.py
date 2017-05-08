#!/usr/bin/env python
'''
Created on May 7, 2017

@author: paepcke
'''
import argparse
import math
import os
import random
import sys
from collections import OrderedDict


class GroupAssigner(object):
    '''
    Multipurpose manager for administering experimental groups.
    Functionality:
    
       - Assign a list of participants to a given set of groups
         Assignment can by choice be randomized or follow the
         order of the given list
       - Given a list of participant-groupName pairs, and a group
         ID, output the participation IDs of only the given group
         
    Group assignments spread participants across the groups of roughly
    equal sizes. Groups and participants are designated by arbitrary
    group identifiers. 
    
    Outputs can be obtained at chosen stages:
    
       - If asked to perform assignment via the assign() method
         a dictionary like this is returned from assigning
         participants [p1,...,p18] into four groups:
    
        		   {group1 : [p1,p2,p3,p4,p17],
        		    group2 : [p5,p6,p7,p8,p18],
        		    group3 : [p9,p10,p11,p12],
        		    group4 : [p13,p14,p15,p16]
        		    }
       
         Participants remaining after equal-size assignments are added to
		 the first groups as needed. In the example above,
		 p17 and 18 were left over after assigning equal
		 numbers. So groups 1 and 2 each have one more member. 
		 
	   - The dictionary returned from assignment can be printed to
	     stdout via the print method, which also allows output of only
	     a given group.
    '''

    def __init__(self, participant_source, group_ids, randomize, only_group='All'):
        '''
        Initializes the group assigner, but does not
        execute the grouping. Call assign() on the 
        resulting object to do the actual work.
        
        @param participant_source: Either a file with participant ids, one per line,
            or a Python list of participant ids, or a list of participant/group lists. 
            If only_group contains a group name then participant_source is expected 
            to be a file containing pairs of 
            participant_id/group_id separated by commas, or a list of tuples, 
            each containing a participant ID and group id.
        @type participant_source: {string|[string]|[(string,string)]}
        @param group_ids: list of group identifiers that will serve as keys in result dict
        @type group_ids: {[string] | None]
        @param randomize: whether or not to randomize the participants. If
            False, participants are assigned in order. If only_group is specified
            this parameter has no effect
        @type type randomize: boolean
        @param only_group: simply output the participant ids of the given group
        @type only_group: string 
        '''

        self.assignments = None

        if type(participant_source) == list:
            # If list is participant_id/group_id couple-tuples,
            # build the assignment dict from it:
            if type(participant_source[0]) == tuple:
                # And initialize the flat list of participants...
                # The following magic turns [['p1','group1'], ['p5', 'group3']] into 
                # a flat ['p1','p5']:
                self.participant_ids = [participant_group_pair[0] for participant_group_pair in participant_source]
                # Similarly: initialize the group_ids:
                group_ids = [participant_group_pair[1] for participant_group_pair in participant_source]
                # Remove duplicates: 
                group_ids = list(OrderedDict.fromkeys(group_ids))
            else:
                # List of just participant ids:
                self.participant_ids = participant_source
        else:
            # Must be file with participant ids:
            with open(participant_source, 'r') as fd:
                all_participant_ids = fd.read().split('\n')
                # Trailing or leading newlines lead to empty 
                # elements in the list; remove those:
                try:
                    while True:
                        all_participant_ids.remove('')
                except:
                    pass
                self.participant_ids = all_participant_ids

        # Now self.participant_ids is in all cases a list of participants:
        if len(self.participant_ids) == 0:
            raise ValueError("Participant list is empty")
        
        # group_ids may be a list of groups, or None
        
        
        # Any other action needs group ids:
        if len(group_ids) == 0:
            raise ValueError("Group list is empty")
        
        self.group_ids = group_ids
        self.randomize  = randomize
        self.only_group = only_group        

    def run(self):

        self.assignments = self.assign()
        if self.only_group != 'All':
            # Wants to print the assignments of one
            # particular group:
            if self.only_group not in self.assignments.keys():
                raise ValueError('Group %s is not one of the provided groups' % self.only_group)
            self.print_assignments(self.only_group)
            return

        self.print_assignments()
            
    def assign(self):
        '''
        Returns a dictionary with each group id as a key.
        Values are lists of participant ids. All groups
        have equal size, except for the first few groups,
        to which remainders are added.
        
        Assumptions: self.participant_ids is a list of
        participant ids, such as email addresses. self.group_ids
        is a list of group identifiers.
        
        :return dictionary of participant lists, keyed by group identifiers.
        :rtype {string:[string]}
        '''
        
        assignments = {}
        
        # Init all groups to empty lists, in case
        # there are not even enough participants to
        # fill all groups:
        
        for group_id in self.group_ids:
            assignments[group_id] = []
        
        # Number of participants per group when
        # groups are equal:
        num_per_group = max(1, int(math.floor(len(self.participant_ids)/len(self.group_ids))))
        
        if self.randomize:
            # Randomize (shuffle modifies list in place):
            random.shuffle(self.participant_ids)
        
        start_index = 0
        for group_id in self.group_ids:
            group_list = self.participant_ids[start_index:start_index + num_per_group]
            if len(group_list) == 0:
                # Ran out of participants to assign. All done:
                return assignments
            assignments[group_id] = group_list
            start_index += num_per_group
        # Distribute any left-overs across groups:
        remainders = len(self.participant_ids) % len(self.group_ids)
        if remainders > 0:
            for remainder in range(remainders):
                assignments[self.group_ids[remainder]].append(self.participant_ids[start_index])
                start_index += 1
            
        return assignments
    
    def print_assignments(self, group='All'):
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
        for group in self.group_ids:
            if self.only_group != 'All' and group != self.only_group:
                continue
            for participant in self.assignments[group]:
                print('%s,%s' % (participant, group))
                
    def build_dict_from_tuples(self, tuples):
        '''
        Given a list of tuples (participant_id, group_id), construct
        a dictionary in which groups are keys, and lists of 
        participants are values. return the dict.
        
        @param tuples: participant_id/group_id pairs
        @type tuples: (string, string)
        @return: dictionary class-->participants
        @rtype: {string : [string]
        '''
        
        assignments = {}
        for (participant, group) in tuples:
            try:
                assignments[group].append(participant)
            except KeyError:
                assignments[group] = [participant]
                
        return assignments
        
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(['-g', '--group'],
                        dest='only_group',
                        default='All',
                        help='Only output the given group'
                        )
    parser.add_argument(['-r', '--randomize'],
                        dest='randomize',
                        require=True,
                        choices=['yes', 'no'],
                        help='Randomize the input'
                        )
    parser.add_argument('participant_source',
                        help='File with list of participant identfiers, such as email address'
                        )
    parser.add_argument('group_identifiers',
                        nargs="*",
                        help='Identifiers of groups into which to randomize; example 1 2 3, or Group1 Group2'
                        )

    args = parser.parse_args();
    
    # From the command line, participant IDs can only
    # be passed in via a file: 
    participant_source = args.participant_source
    try:
        with open(participant_source, 'r') as fd:
            pass
    except IOError:
        print('First argument must be a readable file with a list of participant identifiers.')
        sys.exit(1)

    group_ids = args.group_identifiers
    if len(group_ids) == 0:
        print('Arguments after the first must be group identifiers.')
        sys.exit(1)
 
    randomize = True if args.randomize == 'yes' else False       
    GroupAssigner(participant_source, group_ids, randomize, only_group=args.only_group)
    
