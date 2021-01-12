# Copyright © 2020 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The service that analyzes an array of names."""
# This is important as this will add modules purporting to be Flask modules for later use by the extension.
# Without this, Flask-SQLAlchemy may not work!
# Thanks!
import asyncio
import os
from time import time

import config  # pylint: disable=wrong-import-order; # noqa: I001
import quart.flask_patch
from namex import models
from namex.models import db, ma
from namex.services.name_request.auto_analyse.name_analysis_utils import get_flat_list, get_synonyms_dictionary
from namex.services.name_request.auto_analyse.protected_name_analysis import ProtectedNameAnalysisService
from .analyzer import get_substitutions_dictionary
from quart import Quart, jsonify, request
from swagger_client import SynonymsApi as SynonymService

from .analyzer import auto_analyze, clean_name, get_compound_synonyms, update_name_tokens

# Set config
QUART_APP = os.getenv('QUART_APP')
RUN_MODE = os.getenv('FLASK_ENV', 'production')

quart_app: Quart | None = None


async def create_app(run_mode):
    """Create the app object for configuration and use."""
    try:
        quart_app = Quart(__name__)
        quart_app.logger.debug('APPLICATION CREATED')
        quart_app.config.from_object(config.CONFIGURATION[run_mode])
        db.init_app(quart_app)
        ma.init_app(quart_app)
        quart_app.db = db
    except Exception as err:
        quart_app.logger.debug(
            'Error creating application in auto-analyze service: {0}'.format(repr(err.with_traceback(None))))
        raise


def register_shellcontext(quart_app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {
            'app': quart_app,
            # 'jwt': jwt,
            'db': db,
            'models': models
        }

    quart_app.shell_context_processor(shell_context)


@quart_app.route('/', methods=['POST'])
async def main():
    """Return the outcome of this private service call."""
    name_analysis_service = ProtectedNameAnalysisService()
    service = name_analysis_service
    np_svc_prep_data = service.name_processing_service
    syn_svc = synonym_service
    np_svc_prep_data.prepare_data()

    json_data = await request.get_json()
    list_dist = json_data.get('list_dist')
    list_desc = json_data.get('list_desc')
    list_name = json_data.get('list_name')
    dict_substitution = json_data.get('dict_substitution')
    dict_synonyms = json_data.get('dict_synonyms')
    matches = json_data.get('names')

    app.logger.debug('Number of matches: {0}'.format(len(matches)))

    start_time = time()
    # result = await asyncio.gather(
    #     *[auto_analyze(name, list_name, list_dist, list_desc, dict_substitution, dict_synonyms, np_svc_prep_data)
    #       for
    #       name in matches]
    # )
    name_tokens_clean_dict_list = await asyncio.gather(
        *[clean_name(name, np_svc_prep_data) for name in matches]
    )
    name_tokens_clean_dict = dict(pair for d in name_tokens_clean_dict_list for pair in d.items())

    stand_alone_words = np_svc_prep_data.get_stand_alone_words()

    list_words = list(set(get_flat_list(list(name_tokens_clean_dict.values()))))

    dict_all_simple_synonyms = get_synonyms_dictionary(syn_svc, dict_synonyms, list_words)
    dict_all_compound_synonyms = get_compound_synonyms(service.name_processing_service, name_tokens_clean_dict, syn_svc, dict_all_simple_synonyms)

    dict_all_synonyms = {**dict_synonyms, **dict_all_simple_synonyms}

    # Need to split in compound terms the name
    name_tokens_clean_dict = update_name_tokens(list(dict_all_compound_synonyms.keys()), name_tokens_clean_dict)

    list_words = list(set(get_flat_list(list(name_tokens_clean_dict.values()))))

    dict_all_substitutions = get_substitutions_dictionary(syn_svc, dict_substitution, dict_all_synonyms, list_words)

    result = await asyncio.gather(
        *[auto_analyze(name, name_tokens, list_name, list_dist, list_desc, dict_all_substitutions, dict_all_synonyms, dict_all_compound_synonyms, stand_alone_words, service) for
          name, name_tokens in name_tokens_clean_dict.items()]
    )

    print('--- Conflict analysis for {count} matches in {time} seconds ---'.format(
        count=len(matches),
        time=(time() - start_time)
    ))
    print('--- Average match analysis time: {time} seconds / name ---'.format(
        time=((time() - start_time) / len(matches))
    ))

    return jsonify(result=result)


@quart_app.after_request
def after_request(response):
    if db is not None:
        print('Closing AutoAnalyze service DB connections')
        db.engine.dispose()

    return response


@quart_app.after_request
def add_version(response):  # pylint: disable=unused-variable; linter not understanding framework call
    os.getenv('OPENSHIFT_BUILD_COMMIT', '')
    return response

    register_shellcontext(quart_app)
    await quart_app.app_context().push()
    return quart_app


loop = asyncio.get_event_loop()
loop.set_debug(True)
app = loop.run_until_complete(create_app(RUN_MODE))

if __name__ == '__main__':
    app.run(port=7000, host='localhost')
