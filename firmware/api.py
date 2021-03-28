import picoweb
import ujson as json
import ure as re

import controller
import hal

app = picoweb.WebApp(__name__)


@app.route("/api/status")
def status(req, resp):
    encoded = json.dumps(
        {
            "status": controller.heat_enabled,
            "temperature": hal.temp,
            "setpoint": hal.pid.setpoint,
            "duty": hal.relay.duty(),
            "Kp": hal.pid.Kp,
            "Ki": hal.pid.Ki,
            "Kd": hal.pid.Kd,
        }
    )
    yield from picoweb.start_response(resp, content_type="application/json")
    yield from resp.awrite(encoded)


@app.route("/api/status/off")
def off(req, resp):
    controller.stop_controller()
    yield from status(req, resp)


@app.route("/api/status/on")
def on(req, resp):
    controller.start_controller()
    yield from status(req, resp)


@app.route(re.compile("^/api/pid/(.+)/(.+)"), methods=["PUT"])
def set_pid_param(req, resp):
    params = ("Ki", "Kp", "Kd")
    param = req.url_match.group(1)
    if param not in params:
        raise Exception("Param not in {}".format(params))
    val = float(req.url_match.group(2))

    if val < 0 or val > 1:
        raise Exception("Val in wrong range")
    setattr(hal.pid, param, val)

    yield from status(req, resp)


@app.route(re.compile("^/api/countdown/start/([0-9]+)"), methods=["PUT"])
def set_countdown(req, resp):
    secs = int(req.url_match.group(1))
    controller.start_countdown(secs)
    yield from status(req, resp)


@app.route("/api/countdown/stop", methods=["PUT"])
def stop_countdown(req, resp):
    controller.stop_countdown()
    yield from status(req, resp)


async def run_app():
    app.run(debug=True, host="0.0.0.0", port="80")


def init(loop):
    loop.create_task(run_app())
