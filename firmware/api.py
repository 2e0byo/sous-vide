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
            "countdown": controller.time_remaining,
            "period": hal.period,
            "brightness": hal.disp.brightness(),
        }
    )
    yield from picoweb.start_response(resp, content_type="application/json")
    yield from resp.awrite(encoded)


@app.route(re.compile("/api/setpoint/(.+)"))
def set_setpoint(req, resp):
    val = float(req.url_match.group(1))
    if val < 0 or val > 100:
        raise Exception("Invalid setpoint.")
    hal.pid.setpoint = val
    yield from status(req, resp)


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

    if val < 0:
        raise Exception("Val in wrong range")
    setattr(hal.pid, param, val)
    hal.config[param] = val
    hal.persist_config()

    yield from status(req, resp)


@app.route("/api/pid/reset", methods=["PUT"])
def reset_pid(req, resp):
    hal.pid.reset()
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


@app.route(re.compile("^/api/pwm/freq/(.+)"), methods=["PUT"])
def set_pwm_freq(req, resp):
    freq = float(req.url_match.group(1))
    if freq > 1:
        raise Exception("Val in wrong range")
    hal.relay.freq(freq)
    hal.period = hal.relay._period
    hal.config["freq"] = freq
    hal.persist_config()
    yield from status(req, resp)


@app.route(re.compile("^/api/backlight/([1-9])"), methods=["PUT"])
def set_brightness(req, resp):
    br = int(req.url_match.group(1))
    hal.disp.brightness(br)
    hal.config["brightness"] = br
    hal.persist_config()
    yield from status(req, resp)


@app.route(re.compile("^/api/manual/(.+)"), methods=["PUT"])
def manual_output(req, resp):
    duty = int(req.url_match.group(1))
    if duty < 0 or duty > 1023:
        raise Exception("Invalid input for duty")
    controller.stop_controller()
    hal.relay.duty(duty)
    yield from status(req, resp)


async def run_app():
    app.run(debug=True, host="0.0.0.0", port="80")


def init(loop):
    loop.create_task(run_app())
