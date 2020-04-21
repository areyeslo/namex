class GetSynonymListsMixin(object):
    _prefixes = []
    _synonyms = []
    _substitutions = []
    _stop_words = []
    # TODO: Arturo _number_words is declared in multiple files
    _number_words = []
    _designated_end_eng_words = []
    _designated_end_fr_words = []

    _designated_any_eng_words = []
    _designated_any_fr_words =[]

    _designated_all_words = []

    def get_prefixes(self):
        return self._prefixes

    def get_synonyms(self):
        return self._synonyms

    def get_substitutions(self):
        return self._substitutions

    def get_stop_words(self):
        return self._stop_words

    def get_number_words(self):
        return self._number_words

    def get_designated_end_eng_words(self):
        return self._designated_end_eng_words

    def get_designated_any_eng_words(self):
        return self._designated_any_eng_words

    def get_designated_end_fr_words(self):
        return self._designation_end_fr_words

    def get_designated_any_fr_words(self):
        return self._designated_any_fr_words
