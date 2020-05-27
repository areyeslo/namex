from datetime import date
from string import Template

from collections import deque

from namex.services.name_request.auto_analyse import AnalysisIssueCodes

from namex.utils.service_utils import get_entity_type_description

# Import DTOs
from .response_objects.name_analysis_issue import NameAnalysisIssue
from .response_objects.name_action import NameAction, NameActions, WordPositions
from .response_objects.consenting_body import ConsentingBody
from .response_objects.conflict import Conflict


class AnalysisResponseIssue:
    issue_type = "Issue"  # Maybe get rid of this guy
    header = "Further Action Required"
    status_text = ""
    status = "fa"  # This is a CODE [AV | FA | RC]
    issue = None

    '''
    @:param setup_config Setup[]
    '''

    def __init__(self, analysis_response, setup_config):
        self.analysis_response = analysis_response
        self.name_tokens = analysis_response.name_tokens
        self.entity_type = analysis_response.entity_type
        self.setup_config = []
        self.set_issue_setups(setup_config)

    # TODO: Maybe move this to utils? Do as part of code clean up and refactor task
    @classmethod
    def _lc_list_items(cls, str_list, convert=False):
        if not str_list or type(str_list) is not list:
            return []  # This method should always return a list

        try:
            converted_list = list(map(lambda d: d.upper() if isinstance(d, str) else '', str_list)) \
                if convert else list(map(lambda d: d.upper(), str_list))
        except Exception as err:
            print('List is not a list of strings ' + repr(err))

        return converted_list

    def create_issue(self, procedure_result):
        return self.issue

    '''
    @:param setup_config Setup[]
    '''

    def set_issue_setups(self, setup_config):
        self.setup_config = setup_config

    @classmethod
    def _join_list_words(cls, list_words, separator=", "):
        return "<b>" + separator.join(list_words) + "</b>"

    # Johnson & Johnson Engineering will return original tokens:
    # [Johnson, &, Johnson, Engineering]
    # and return name tokens:
    # [Johnson, Engineering]

    # Johnson & Johnson & Johnson Engineering will return original tokens:
    # [Johnson, &, Johnson, &, Johnson, Engineering]
    # and return name tokens:
    # [Johnson, Engineering]

    # John Deere Deere Engineering will return original tokens:
    # [John, Deere, Deere, Engineering]
    # and return name tokens:
    # [John, Deere, Engineering]

    # John Deere & Deere Engineering will return original tokens:
    # [John, Deere, &, Deere, Engineering]
    # and return name tokens:
    # [John, Deere, Engineering]

    # John Deere John Engineering will return original tokens:
    # [John, Deere, John, Engineering]
    # and return name tokens:
    # [John, Deere, John, Engineering]

    # J & L Engineering will return original tokens:
    # [J, &, L, Engineering]
    # and return name tokens:
    # [JL, Engineering]

    # J & L & L Engineering will return original tokens:
    # [J, &, L, &, L, Engineering]
    # and return name tokens:
    # [JLL, Engineering]
    def get_next_token_if_composite(self, str_name, name_original_tokens, name_processed_tokens):
        token_string = ''
        processed_name_string = ''

        original_tokens = deque(name_original_tokens)
        processed_tokens = deque(name_processed_tokens)

        if len(processed_tokens) == 0:
            return False, 0, 0, None

        processed_token = processed_tokens.popleft()
        current_processed_token = processed_token

        processed_token_count = 0
        composite_idx_offset = 0
        current_original_token = original_tokens.popleft()

        if current_processed_token == current_original_token:
            return False, 0, 0, current_original_token

        if current_processed_token.find(current_original_token) == -1:
            return False, 0, 0, current_original_token

        while len(original_tokens) >= 0:
            if token_string == processed_token:
                break

            processed_token_count += 1

            processed_name_string += current_original_token

            token_substr_idx = current_processed_token.find(current_original_token)
            token_is_next_chunk = token_substr_idx == 0
            if token_is_next_chunk:
                current_processed_token = current_processed_token[len(current_original_token):]
                token_string += current_original_token

            next_char = False
            # this_char = str_name[len(original_name_string) - 1]
            if len(str_name) > len(processed_name_string):
                next_char = str_name[len(processed_name_string)]

            if next_char and next_char == ' ':
                processed_name_string += ' '

            if next_char and next_char == ' ' or not next_char:
                composite_idx_offset += 1

            if len(original_tokens) > 0:
                current_original_token = original_tokens.popleft()

        if processed_token_count:
            return processed_token, processed_token_count, composite_idx_offset, processed_name_string

        return False, 0, 0, current_processed_token

    def adjust_word_index(self, original_name_str, name_original_tokens, name_tokens, word_idx,
                          offset_designations=True):
        all_designations = self.analysis_response.analysis_service.get_all_designations()
        # all_designations_user = self.analysis_response.analysis_service.get_all_designations_user()

        original_tokens = deque(name_original_tokens)
        processed_tokens = deque(name_tokens)
        processed_token_idx = 0

        target_word = name_tokens[word_idx]

        word_idx_offset = 0
        composite_token_offset = 0

        previous_original_token = None
        current_original_token = None

        unprocessed_name_string = original_name_str.lower()

        while len(original_tokens) > 0:
            # Check to see if we're dealing with a composite, if so, get the offset amount
            composite_token, composite_tokens_processed, composite_idx_offset, processed_name_string = \
                self.get_next_token_if_composite(unprocessed_name_string, original_tokens, processed_tokens)

            if processed_name_string:
                # Only replace the first match!
                unprocessed_name_string = unprocessed_name_string.replace(processed_name_string, '', 1).strip()

            # Handle composite tokens
            if composite_token:
                current_original_token = composite_token

                if composite_idx_offset > 0:
                    composite_token_offset += composite_idx_offset - 1

                for x in range(0, composite_tokens_processed):
                    if len(original_tokens) > 0:
                        original_tokens.popleft()

            # Handle normal word tokens
            else:
                if len(original_tokens) > 0:
                    # Pop the left-most token off the list
                    current_original_token = original_tokens.popleft()

                    # If there are no processed tokens left to deal with, skip this step (handles designations, etc.)
                    # We don't need to increment the word_idx_offset anymore unless there's a repeated token
                    if len(processed_tokens) > 0:
                        if offset_designations:
                            # Does the current word have any punctuation associated with?
                            next_char = ''
                            if len(unprocessed_name_string) > 0 and len(original_tokens) > 0 and \
                                    unprocessed_name_string[0] == original_tokens[0]:
                                next_char = original_tokens[0]

                            token_is_designation = (current_original_token + next_char) in all_designations
                            if original_tokens and token_is_designation:
                                original_tokens.popleft()
                                unprocessed_name_string = unprocessed_name_string[1:].strip()

                            # Skip designations
                            if token_is_designation or current_original_token not in name_tokens:
                                word_idx_offset += 1
                                continue
                        else:
                            if current_original_token not in name_tokens:
                                word_idx_offset += 1
                                continue

            # Check for repeated tokens - this has been moved to get_next_token_if_composite
            # if current_original_token == previous_original_token:
                # word_idx_offset += 1

            # We only need to run this until we encounter the specified word
            if current_original_token == target_word and word_idx == processed_token_idx:
                original_tokens.clear()  # Clear the rest of the items to break out of the loop, we're done!
                continue

            # if previous_original_token != current_original_token and len(processed_tokens) > 0:
            if len(processed_tokens) > 0:
                processed_token_idx += 1
                processed_tokens.popleft()

            previous_original_token = current_original_token

        offset_idx = word_idx + word_idx_offset + composite_token_offset

        print('Adjusted word index for word [' + target_word + '] from [' + str(word_idx) + '] -> [' + str(
            offset_idx) + ']')

        return offset_idx, word_idx, word_idx_offset, composite_token_offset


class CheckIsValid(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.CHECK_IS_VALID
    status_text = "Approved"
    issue = None

    def create_issue(self, procedure_result):
        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1=None,
            line2=None,
            consenting_body=None,
            designations=None,
            show_reserve_button=None,
            show_examination_button=None,
            conflicts=None,
            setup=None,
            name_actions=None
        )

        return issue


"""
Word Classification Engine Issues
"""

'''
@:deprecated
'''


# TODO: Get RID OF THIS!!!


class IncorrectCategory(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.INCORRECT_CATEGORY
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="Category of the word is incorrect.",
            line2=None,
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=True,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        issue.name_actions = [
            NameAction(
                type=NameActions.HIGHLIGHT
            )
        ]

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


"""
Well-Formed Name Issues
"""


class ContainsUnclassifiableWordIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.CONTAINS_UNCLASSIFIABLE_WORD
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name = self._lc_list_items(self.analysis_response.name_tokens)  # procedure_result.values['list_name']
        list_none = self._lc_list_items(procedure_result.values['list_none'])

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="The word(s) " + self._join_list_words(list_none) + " have not previously been approved for use.",
            line2="Please check wait times at the top of the screen.",
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        # TODO: Fix the case eg. 'Asdfadsf Something Asdfadsf Company Ltd.'...
        #  If there's a duplicate of an unclassified word, just grabbing the index won't do!
        issue.name_actions = []
        for word in list_none:
            offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                self.analysis_response.name_as_submitted,
                self.analysis_response.name_original_tokens,
                self.analysis_response.name_tokens,
                list_name.index(word)
            )

            issue.name_actions.append(
                NameAction(
                    type=NameActions.HIGHLIGHT,
                    word=word,
                    index=offset_idx
                )
            )

        # Setup boxes
        issue.setup = self.setup_config
        # Replace template strings in setup boxes
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


class AddDistinctiveWordIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.ADD_DISTINCTIVE_WORD
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="Requires a word at the beginning of your name that sets it apart.",
            line2=None,
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        list_name = self._lc_list_items(self.analysis_response.name_tokens)

        issue.name_actions = [
            NameAction(
                type=NameActions.BRACKETS,
                position=WordPositions.START,
                message="Add a Word Here",
                word=list_name[0] if list_name.__len__() > 0 else None,
                index=0
            )
        ]

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


class AddDescriptiveWordIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.ADD_DESCRIPTIVE_WORD
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name = self._lc_list_items(self.analysis_response.name_tokens)  # procedure_result.values['list_name']
        list_dist = self._lc_list_items(procedure_result.values['list_dist'])

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="Requires a word that describes the nature of your business.",
            line2=None,
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        last_dist_word = list_dist[-1] if list_dist.__len__() > 0 else None
        # TODO: Why was this like this before?
        # dist_word_idx = list_name.index(last_dist_word) # if list_dist.__len__() > 0 else 0
        dist_word_idx = list_name.index(last_dist_word) if list_dist.__len__() > 0 else 0
        offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
            self.analysis_response.name_as_submitted,
            self.analysis_response.name_original_tokens,
            self.analysis_response.name_tokens,
            dist_word_idx
        )

        issue.name_actions = [
            NameAction(
                type=NameActions.BRACKETS,
                position=WordPositions.END,
                message="Add a Descriptive Word Here",
                word=last_dist_word,
                index=offset_idx
            )
        ]

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


class TooManyWordsIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.TOO_MANY_WORDS
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="Names longer than three words, not including proper designations, may be sent to examination.",
            line2="Please check wait times at the top of the screen.",
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=True,
            conflicts=None,
            setup=None,
            name_actions=None
        )

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


"""
General Name Issues
"""


class ContainsWordsToAvoidIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.WORDS_TO_AVOID
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name = self._lc_list_items(self.analysis_response.name_tokens)  # procedure_result.values['list_name']
        list_avoid = self._lc_list_items(procedure_result.values['list_avoid'])
        list_avoid_compound = self._lc_list_items(procedure_result.values['list_avoid_compound'])

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="The word(s) " + self._join_list_words(list_avoid_compound) + " cannot be used.",
            line2="",
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        # TODO: If there's a duplicate of a word to avoid, just grabbing the index might not do!
        issue.name_actions = []
        for word in list_avoid:
            offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                self.analysis_response.name_as_submitted,
                self.analysis_response.name_original_tokens,
                self.analysis_response.name_tokens,
                list_name.index(word)
            )

            issue.name_actions.append(
                NameAction(
                    type=NameActions.STRIKE,
                    word=word,
                    index=offset_idx
                )
            )

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


class WordSpecialUse(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.WORD_SPECIAL_USE
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name = self._lc_list_items(self.analysis_response.name_tokens)  # procedure_result.values['list_name']
        list_special = self._lc_list_items(procedure_result.values['list_special'])
        list_special_compound = self._lc_list_items(procedure_result.values['list_special_compound'])

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="The word(s) " + self._join_list_words(list_special_compound) + " must go to examination ",
            line2=None,
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        # TODO: If there's a duplicate of a word to avoid, just grabbing the index might not do!
        issue.name_actions = []
        for word in list_special:
            offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                self.analysis_response.name_as_submitted,
                self.analysis_response.name_original_tokens,
                self.analysis_response.name_tokens,
                list_name.index(word)
            )

            issue.name_actions.append(
                NameAction(
                    type=NameActions.HIGHLIGHT,
                    word=word,
                    index=offset_idx
                )
            )

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


class NameRequiresConsentIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.NAME_REQUIRES_CONSENT
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name = self.analysis_response.name_tokens  # procedure_result.values['list_name']
        list_consent = self._lc_list_items(procedure_result.values['list_consent'])
        list_consent_original = self._lc_list_items(procedure_result.values['list_consent_original'])

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="The word(s) " + self._join_list_words(list_consent_original) + " are restricted and may require consent.",
            line2="Please check the options below.",
            consenting_body=ConsentingBody(
                name="",
                email=""
            ),
            designations=None,
            show_reserve_button=None,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        issue.name_actions = []
        for word in list_consent:
            offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                self.analysis_response.name_as_submitted,
                self.analysis_response.name_original_tokens,
                self.analysis_response.name_tokens,
                list_name.index(word.lower())
            )

            issue.name_actions.append(
                NameAction(
                    type=NameActions.HIGHLIGHT,
                    word=word,
                    index=offset_idx
                )
            )

        # TODO: Where does this info come from?
        issue.consenting_body = ConsentingBody(
            name="Example Conflict Company Ltd.",
            email="email@example.com"
        )

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


class CorporateNameConflictIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.CORPORATE_CONFLICT
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        name_as_submitted = self.analysis_response.name_as_submitted
        list_original = self._lc_list_items(self.analysis_response.name_original_tokens)
        list_name = self._lc_list_items(self.analysis_response.name_tokens)

        all_designations = self._lc_list_items(self.analysis_response.analysis_service.get_all_designations())

        list_name_as_submitted = self._lc_list_items(self.analysis_response.name_as_submitted_tokenized)
        # Filter out designations from the tokens
        list_tokens = [item for item in list_name_as_submitted if item not in all_designations]

        list_dist = procedure_result.values['list_dist']  # Don't lower case this one it's a list wrapped list
        list_desc = procedure_result.values['list_desc']  # Don't lower case this one it's a list wrapped list
        list_conflicts = procedure_result.values['list_conflicts']  # Don't lower case this one it's a dict
        list_corp_num = procedure_result.values['corp_num']
        list_consumption_date = procedure_result.values['consumption_date']

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="Too similar to an existing name.",
            line2=None,
            consenting_body=None,
            designations=None,
            show_reserve_button=None,
            show_examination_button=False,
            conflicts=[],
            setup=None,
            name_actions=[]
        )

        '''
        eg:
        list_name: <class 'list'>: ['mountain', 'view', 'growers']
        list_dist: <class 'list'>: [['mountain'], ['mountain', 'view']]
        list_desc: <class 'list'>: [['view', 'growers'], ['growers']]
        list_conflicts: <class 'dict'>: {'MOUNTAIN VIEW GROWERS INC.': {'mountain': ['mountain'], 'view': ['view'], 'growers': ['growers']}}
        '''

        # Grab the first conflict
        current_conflict_name = list(list_conflicts.keys())[0]  # eg: 'MOUNTAIN VIEW GROWERS INC.'
        current_corp_num = list_corp_num[0]
        current_consumption_date = list_consumption_date[0]
        current_conflict = list_conflicts[
            current_conflict_name]  # eg: {'mountain': ['mountain'], 'view': ['view'], 'growers': ['growers']}
        current_conflict_keys = list(current_conflict.keys()) if current_conflict else []

        is_exact_match = (list_name == current_conflict_keys)

        list_dist_words = list(set([item for sublist in list_dist for item in sublist]))
        list_desc_words = list(set([item for sublist in list_desc for item in sublist]))

        # Apply our is_exact_match strategy:
        # - Add brackets after the first distinctive word
        # - Add brackets after the last descriptive word?
        # - Strike out the last word

        list_remove = []  # These are passed down to the Template

        if is_exact_match:
            # Loop over the token words, we need to decide to do with each word
            for token_idx, word in enumerate(list_tokens):
                offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                    name_as_submitted,
                    list_original,
                    list_tokens,
                    token_idx
                )

                # Highlight the conflict words
                if list_tokens.index(word) != list_tokens.index(list_tokens[-1]):
                    issue.name_actions.append(NameAction(
                        word=word,
                        index=offset_idx,
                        endIndex=offset_idx,
                        type=NameActions.HIGHLIGHT
                    ))

                # Strike out the last matching word
                if list_tokens.index(word) == list_tokens.index(list_tokens[-1]):
                    list_remove.append(word)
                    issue.name_actions.append(NameAction(
                        word=word,
                        index=offset_idx,
                        endIndex=offset_idx,
                        type=NameActions.STRIKE
                    ))

        if not is_exact_match:
            # Loop over the list_name words, we need to decide to do with each word
            for token_idx, word in enumerate(list_tokens):
                offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                    name_as_submitted,
                    list_original,
                    list_tokens,
                    token_idx
                )

                # This code has duplicate blocks because it allows us to tweak the response for composite token matches separately from normal words if necessary
                if composite_token_offset and composite_token_offset > 0:
                    # <class 'list'>: ['mountain', 'view']
                    # Highlight the conflict words
                    if word in current_conflict_keys and current_conflict_keys.index(
                            word) != current_conflict_keys.index(current_conflict_keys[-1]):
                        issue.name_actions.append(NameAction(
                            word=word,
                            index=offset_idx,
                            type=NameActions.HIGHLIGHT
                        ))

                    # Strike out the last matching word
                    if word in current_conflict_keys and current_conflict_keys.index(
                            word) == current_conflict_keys.index(current_conflict_keys[-1]):
                        issue.name_actions.append(NameAction(
                            word=word,
                            index=offset_idx,
                            type=NameActions.STRIKE
                        ))
                else:
                    # Highlight the conflict words
                    if word in current_conflict_keys and current_conflict_keys.index(
                            word) != current_conflict_keys.index(current_conflict_keys[-1]):
                        issue.name_actions.append(NameAction(
                            word=word,
                            index=offset_idx,
                            type=NameActions.HIGHLIGHT
                        ))

                    # Strike out the last matching word
                    if word in current_conflict_keys and current_conflict_keys.index(
                            word) == current_conflict_keys.index(current_conflict_keys[-1]):
                        issue.name_actions.append(NameAction(
                            word=word,
                            index=offset_idx,
                            type=NameActions.STRIKE
                        ))

        issue.conflicts = []

        conflict = Conflict(
            name=current_conflict_name,
            date=date.today(),
            corp_num=current_corp_num,
            consumption_date=current_consumption_date
        )

        issue.conflicts.append(conflict)

        # Setup boxes
        issue.setup = self.setup_config
        # Replace template strings in setup boxes
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute({
                        'list_name': self._join_list_words(list_name),
                        'list_remove': self._join_list_words(list_remove),
                        'list_dist': self._join_list_words(list_dist_words),
                        'list_desc': self._join_list_words(list_desc_words)
                    }))

        return issue


class DesignationNonExistentIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.DESIGNATION_NON_EXISTENT
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name = self._lc_list_items(self.analysis_response.name_tokens)  # procedure_result.values['list_name']
        correct_designations = self._lc_list_items(procedure_result.values['correct_designations'])

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="Further Action. A designation is required. Please select one from Option 1 below.",
            line2=None,
            consenting_body=None,
            designations=correct_designations,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        # Setup boxes
        issue.setup = self.setup_config
        # Replace template strings in setup boxes
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute({
                        'list_name': self._join_list_words(list_name),
                        'correct_designations': self._join_list_words(correct_designations)
                    }))

        return issue


class DesignationMismatchIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.DESIGNATION_MISMATCH
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name = self.analysis_response.name_tokens
        list_name_incl_designation = self.analysis_response.name_original_tokens

        incorrect_designations = procedure_result.values['incorrect_designations']
        correct_designations = procedure_result.values['correct_designations']

        incorrect_designations_lc = self._lc_list_items(incorrect_designations, True)
        correct_designations_lc = self._lc_list_items(correct_designations, True)
        list_name_incl_designation_lc = self._lc_list_items(list_name_incl_designation)

        entity_type_description = get_entity_type_description(self.entity_type)

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="The " + self._join_list_words(incorrect_designations_lc) + " designation(s) cannot be used with selected entity type of " + entity_type_description + " </b>",
            line2=None,
            consenting_body=None,
            designations=correct_designations_lc,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        # Loop over the list_name words, we need to decide to do with each word
        for word in list_name_incl_designation_lc:
            offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                self.analysis_response.name_as_submitted,
                self.analysis_response.name_original_tokens,
                list_name_incl_designation_lc,
                list_name_incl_designation.index(word.lower()),
                False
            )

            # Highlight the issues
            if word in incorrect_designations_lc:
                issue.name_actions.append(NameAction(
                    word=word,
                    index=offset_idx,
                    type=NameActions.HIGHLIGHT
                ))

        # Setup boxes
        issue.setup = self.setup_config
        # Replace template strings in setup boxes
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute({
                        'list_name': self._join_list_words(list_name),
                        'correct_designations': self._join_list_words(correct_designations_lc),
                        'incorrect_designations': self._join_list_words(incorrect_designations_lc),
                        'entity_type': self.entity_type  # TODO: Map this CODE!
                    }))

        return issue


class DesignationMoreThanOneIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.DESIGNATION_MORE_THAN_ONE
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name_incl_designation = self.analysis_response.name_original_tokens
        correct_end_designations = procedure_result.values['correct_end_designations']

        correct_end_designations_lc = self._lc_list_items(correct_end_designations, True)
        list_name_incl_designation_lc = self._lc_list_items(list_name_incl_designation)

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="There can be only one designation. You must choose either " + self._join_list_words(
                correct_end_designations_lc, "</b>  or  <b>"),
            line2=None,
            consenting_body=None,
            designations=correct_end_designations,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        # Loop over the list_name words, we need to decide to do with each word
        for word in list_name_incl_designation_lc:
            offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                self.analysis_response.name_as_submitted,
                self.analysis_response.name_original_tokens,
                list_name_incl_designation_lc,
                list_name_incl_designation.index(word),
                False
            )

            # Highlight the issues
            if word in correct_end_designations_lc:
                issue.name_actions.append(NameAction(
                    word=word,
                    index=offset_idx,
                    type=NameActions.HIGHLIGHT
                ))

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue


class DesignationMisplacedIssue(AnalysisResponseIssue):
    issue_type = AnalysisIssueCodes.DESIGNATION_MISPLACED
    status_text = "Further Action Required"
    issue = None

    def create_issue(self, procedure_result):
        list_name_incl_designation = self.analysis_response.name_original_tokens

        misplaced_end_designation = procedure_result.values['misplaced_end_designation']
        misplaced_end_designation_lc = self._lc_list_items(misplaced_end_designation, True)
        list_name_incl_designation_lc = self._lc_list_items(list_name_incl_designation)

        issue = NameAnalysisIssue(
            issue_type=self.issue_type,
            line1="The " + self._join_list_words(
                misplaced_end_designation_lc) + " designation(s) must be at the end of the name.",
            line2=None,
            consenting_body=None,
            designations=None,
            show_reserve_button=False,
            show_examination_button=False,
            conflicts=None,
            setup=None,
            name_actions=[]
        )

        # Loop over the list_name words, we need to decide to do with each word
        for word in list_name_incl_designation_lc:
            offset_idx, word_idx, word_idx_offset, composite_token_offset = self.adjust_word_index(
                self.analysis_response.name_as_submitted,
                self.analysis_response.name_original_tokens,
                list_name_incl_designation_lc,
                list_name_incl_designation.index(word.lower()),
                False
            )

            # Highlight the issues
            if word in misplaced_end_designation_lc:
                issue.name_actions.append(NameAction(
                    word=word,
                    index=offset_idx,
                    type=NameActions.HIGHLIGHT
                ))

        # Setup boxes
        issue.setup = self.setup_config
        for setup_item in issue.setup:
            # Loop over properties
            for prop in vars(setup_item):
                if isinstance(setup_item.__dict__[prop], Template):
                    # Render the Template string, replacing placeholder vars
                    setattr(setup_item, prop, setup_item.__dict__[prop].safe_substitute([]))

        return issue
