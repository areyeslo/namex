import json
from urllib.parse import unquote_plus

from flask import request, jsonify

from namex.services.statistics.wait_time_statistics import WaitTimeStatsService
from namex.services.exceptions import ApiServiceException
from namex.utils.logging import setup_logging
from flask_restplus import Namespace, Resource, cors, fields
from flask_jwt_oidc import AuthError

from http import HTTPStatus

from namex.utils.util import cors_preflight
from namex.utils.api_resource import log_error, handle_exception, get_query_param_str

setup_logging()  # important to do this first

# Register a local namespace for the requests
api = Namespace('waitTimeStats', description='API for Wait Time Statistics')

wait_time_stats = api.model('wait_time_stats', {
    'priority': fields.String
})


@api.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


@cors_preflight('GET')
@api.route('/', strict_slashes=False, methods=['GET', 'OPTIONS'])
class WaitTimeStats(Resource):
    @staticmethod
    @cors.crossdomain(origin='*')
    @api.doc(params={
        'priority': 'Requests priority [Y/N]'
    })
    def get():
        priority_str = get_query_param_str('priority')
        is_priority = True if priority_str and priority_str.lower() == 'y' else False
        try:
            service = WaitTimeStatsService()
            response = service.calculate_examination_rate(is_priority)

            if not response:
                raise ApiServiceException(message='WaitTimeStatsService did not return a result')

            return jsonify(response),HTTPStatus.OK

        except ValueError as err:
            return jsonify('Wait time stats not found: ' + repr(err)), 200
        except ApiServiceException as err:
            return handle_exception(err, err.message, 400)
        except Exception as err:
            return jsonify('Internal Server Error\n' + repr(err)), 500
