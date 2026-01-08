import azure.functions as func
import logging
import json
import requests
from datetime import datetime

app = func.FunctionApp()

@app.route(route="fetch_departures", auth_level=func.AuthLevel.FUNCTION)
def fetch_departures(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('iRail function triggered')
    
    # Get station from query parameter
    station = req.params.get('station', 'Brussels-South')
    
    try:
        # Call iRail API
        url = f"https://api.irail.be/liveboard/"
        params = {"station": station, "format": "json", "lang": "en"}
        headers = {"User-Agent": "BeCodeAzureProject/1.0"}
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Parse response
        station_info = data.get('stationinfo', {})
        departures = data.get('departures', {}).get('departure', [])
        
        # Handle single departure as dict
        if isinstance(departures, dict):
            departures = [departures]
        
        # Build simple response
        result = {
            "status": "success",
            "station": station,
            "station_id": station_info.get('id', ''),
            "departures_count": len(departures),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "departures": [
                {
                    "destination": dep.get('station', ''),
                    "time": datetime.utcfromtimestamp(int(dep.get('time', 0))).strftime('%H:%M'),
                    "platform": dep.get('platform', ''),
                    "delay_minutes": int(dep.get('delay', 0)) // 60,
                    "vehicle": dep.get('vehicleinfo', {}).get('shortname', '')
                }
                for dep in departures[:10]  # Limit to first 10
            ]
        }
        
        return func.HttpResponse(
            json.dumps(result, indent=2),
            mimetype="application/json",
            status_code=200
        )
    
    except requests.RequestException as e:
        logging.error(f"API error: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=502
        )
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=500
        )
