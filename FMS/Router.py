from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from jsonschema.exceptions import ValidationError

from Utils import Point
import FMS
from jsonschema import validate
from threading import Thread

app = Flask(__name__)
sock = SocketIO(app)

@app.route("/")
def serve_root():
    return "FMS is alive"

@app.route("/teams")
def serve_teams():
    data = []
    with FMS.mutex:
        # Create list of teams with desired information
        for team in FMS.teams.values():
            data.append({
                "number": team.number,
                "money": team.money,
                "karma": team.karma,
                "currentFare": team.currentFare,
                "position": {
                    "x": team.pos.x,
                    "y": team.pos.y
                },
                "lastPosUpdate": team.lastPosUpdate
            })
    return jsonify(data)

@app.route("/fares")
def serve_fares():
    data = []
    allOpt = request.args.get("all", default=False, type=lambda st: st.lower() == "true")
    with FMS.mutex:
        # Create copied list of data with desired information
        for idx, fare in enumerate(FMS.fares):
            if fare.isActive or allOpt:
                data.append({
                    "id": idx,
                    "src": {
                        "x": fare.src.x,
                        "y": fare.src.y
                    },
                    "dest": {
                        "x": fare.dest.x,
                        "y": fare.dest.y
                    },
                    "claimed": fare.team is not None,
                    "active": fare.isActive,
                    "expiry": fare.expiry,
                    "inPosition": fare.inPosition,
                    "pickedUp": fare.pickedUp,
                    "completed": fare.completed
                })
        return jsonify(data)

@app.route("/fares/claim/<int:idx>/<int:team>")
def claim_fare(idx: int, team: int):
    with FMS.mutex:
        success = False
        message = ""
        if team in FMS.teams.keys():
            if idx < len(FMS.fares):
                if FMS.fares[idx].claim_fare(team):
                    FMS.teams[team].currentFare = idx
                    success = True
                else:
                    message = "Fare already claimed"
            else:
                message = f"Could not find fare with ID {id}"
        else:
            message = f"Team {team} not in this match"

        return jsonify({
            "success": success,
            "message": message
        })

@app.route("/fares/current/<int:team>")
def current_fare(team: int):
    with FMS.mutex:
        fare_dict = None
        message = ""
        if team in FMS.teams.keys():
            fare_idx = FMS.teams[team].currentFare
            if fare_idx is None:
                message = f"Team {team} does not have an active fare"
            else:
                fare = FMS.fares[fare_idx]
                fare_dict = {
                    "id": fare_idx,
                    "src": {
                        "x": fare.src.x,
                        "y": fare.src.y
                    },
                    "dest": {
                        "x": fare.dest.x,
                        "y": fare.dest.y
                    },
                    "claimed": fare.team is not None,
                    "active": fare.isActive,
                    "expiry": fare.expiry,
                    "inPosition": fare.inPosition,
                    "pickedUp": fare.pickedUp,
                    "completed": fare.completed
                }
        else:
            message = f"Team {team} not in this match"

        return jsonify({
            "fare": fare_dict,
            "message": message
        })

@app.route("/whereami/<int:team>")
def whereami_get(team: int):
    point = None
    last_update : int = 0
    message = ""
    if team in FMS.teams.keys():
        team = FMS.teams[team]
        point = {
            "x": team.pos.x,
            "y": team.pos.y
        },
        last_update = team.lastPosUpdate
    else:
        message = f"Team {team} not in this match"

    return jsonify({
        "position": point,
        "last_update": last_update,
        "message": message
    })

# Socket endpoints
@sock.on("connect")
def sock_connect(auth):
    print("Connected")

@sock.on("disconnect")
def sock_disconnect():
    print("Disconnected")

whereami_update_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "team": {"type": "number"},
            "x": {"type": "number"},
            "y": {"type": "number"},
        },
        "required": ["team", "x", "y"],
    },
}
@sock.on("whereami_update")
def whereami_update(json):
    # Data should be JSON payload with [{team:int, x:float, y:float}]
    # Log sending address, should be whitelisted in production
    print(f"Recv whereami update from {request.remote_addr}")
    # Validate payload
    try:
        validate(json, schema=whereami_update_schema)
        for entry in json:
            team = entry['team']
            x = entry['x']
            y = entry['y']
            if team in FMS.teams.keys():
                FMS.teams[team].update_position(Point(x, y))
            else:
                print(f"Team not in match {team}")
    except ValidationError as e:
        print(f"Validation failed: {e}")

if __name__ == "__main__":
    Thread(target=FMS.periodic, daemon=True).start()
    sock.run(app, allow_unsafe_werkzeug=True)