from urllib.parse import unquote_plus

from flask import request, make_response, jsonify

from namex.services.statistics.wait_time_statistics import WaitTimeStatsService
from namex.utils.logging import setup_logging
from flask_restplus import Namespace, Resource, cors, fields
from flask_jwt_oidc import AuthError

from http import HTTPStatus

from namex.utils.util import cors_preflight

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
@api.route('/', strict_slashes=False, methods=['GET''OPTIONS'])
class WaitTimeStats(Resource):
    @staticmethod
    @cors.crossdomain(origin='*')
    @api.doc(params={
        'priority': 'Requests priority [Y/N]'
    })
    def get():
        priority = unquote_plus(request.args.get('priority').strip()) if request.args.get('priority') else None
        try:
            service = WaitTimeStatsService()
            entity = service.calculate_examination_rate(priority)

            if not entity:
                raise ValueError('WaitTimeStatsService did not return a result')

            return HTTPStatus.OK

        except ValueError as err:
            return jsonify('Wait time stats not found: ' + repr(err)), HTTPStatus.NOT_FOUND
        except Exception as err:
            return jsonify('Internal server error: ' + repr(err)), HTTPStatus.INTERNAL_SERVER_ERROR
