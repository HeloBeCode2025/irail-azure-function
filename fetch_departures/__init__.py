import azure.functions as func
import logging
import json
import os
import pymssql
import requests
from datetime import datetime


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to fetch train departures from iRail API
    and store them in Azure SQL Database.
    
    Query Parameters:
        station (str): Station name, default "Brussels-South"
    
    Returns:
        JSON response with fetch results
    """
    logging.info('iRail Fetch Departures function triggered')
    
    # Get station from query parameter, default to Brussels-South
    station = req.params.get('station', 'Brussels-South')
    
    try:
        # =====================
        # STEP 1: Fetch from iRail API
        # =====================
        irail_url = "https://api.irail.be/liveboard/"
        params = {
            "station": station,
            "format": "json",
            "lang": "en"
        }
        headers = {
            "User-Agent": "BeCodeAzureProject/1.0 (learning@becode.org)"
        }
        
        logging.info(f"Calling iRail API for station: {station}")
        response = requests.get(irail_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # =====================
        # STEP 2: Parse the response
        # =====================
        station_info = data.get('stationinfo', {})
        departures_data = data.get('departures', {})
        departures = departures_data.get('departure', [])
        
        # Handle case where API returns single departure as dict instead of list
        if isinstance(departures, dict):
            departures = [departures]
        
        logging.info(f"Fetched {len(departures)} departures for {station}")
        
        # =====================
        # STEP 3: Connect to Azure SQL
        # =====================
        server = os.environ.get('SQL_SERVER')
        database = os.environ.get('SQL_DATABASE')
        username = os.environ.get('SQL_USERNAME')
        password = os.environ.get('SQL_PASSWORD')
        
        if not all([server, database, username, password]):
            missing = [k for k, v in {
                'SQL_SERVER': server,
                'SQL_DATABASE': database,
                'SQL_USERNAME': username,
                'SQL_PASSWORD': password
            }.items() if not v]
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"Missing environment variables: {missing}"
                }),
                mimetype="application/json",
                status_code=500
            )
        
        logging.info(f"Connecting to database: {database} on {server}")
        conn = pymssql.connect(
            server=server,
            user=username,
            password=password,
            database=database
        )
        cursor = conn.cursor()
        
        # =====================
        # STEP 4: Upsert station info
        # =====================
        station_id = station_info.get('id', '')
        if station_id:
            cursor.execute("""
                MERGE INTO stations AS target
                USING (SELECT %s AS station_id, %s AS name, %s AS standard_name, 
                              %s AS latitude, %s AS longitude) AS source
                ON target.station_id = source.station_id
                WHEN MATCHED THEN
                    UPDATE SET name = source.name, 
                               standard_name = source.standard_name,
                               latitude = source.latitude, 
                               longitude = source.longitude
                WHEN NOT MATCHED THEN
                    INSERT (station_id, name, standard_name, latitude, longitude)
                    VALUES (source.station_id, source.name, source.standard_name, 
                            source.latitude, source.longitude);
            """, (
                station_id,
                station_info.get('name', ''),
                station_info.get('standardname', ''),
                station_info.get('locationY'),  # latitude
                station_info.get('locationX')   # longitude
            ))
            logging.info(f"Upserted station: {station_id}")
        
        # =====================
        # STEP 5: Insert departures
        # =====================
        inserted_count = 0
        skipped_count = 0
        
        for dep in departures:
            departure_id = dep.get('departureConnection', '')
            
            # Skip if no departure ID
            if not departure_id:
                skipped_count += 1
                continue
            
            # Check if this departure already exists
            cursor.execute(
                "SELECT 1 FROM departures WHERE departure_id = %s", 
                (departure_id,)
            )
            if cursor.fetchone():
                skipped_count += 1
                continue
            
            # Convert Unix timestamp to datetime
            try:
                scheduled_time = datetime.utcfromtimestamp(int(dep.get('time', 0)))
            except (ValueError, TypeError):
                logging.warning(f"Invalid time for departure: {departure_id}")
                skipped_count += 1
                continue
            
            # Get nested info
            vehicle_info = dep.get('vehicleinfo', {})
            dest_station_info = dep.get('stationinfo', {})
            platform_info = dep.get('platforminfo', {})
            occupancy_info = dep.get('occupancy', {})
            
            # Insert the departure
            cursor.execute("""
                INSERT INTO departures (
                    departure_id, station_id, destination_id, destination_name,
                    scheduled_time, delay_seconds, platform, vehicle_id, 
                    vehicle_short, is_canceled, has_left, occupancy, fetched_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, GETUTCDATE())
            """, (
                departure_id,
                station_id,
                dest_station_info.get('id', ''),
                dep.get('station', ''),  # destination name
                scheduled_time,
                int(dep.get('delay', 0)),
                platform_info.get('name', str(dep.get('platform', ''))),
                dep.get('vehicle', ''),
                vehicle_info.get('shortname', ''),
                1 if dep.get('canceled', 0) == 1 else 0,
                1 if dep.get('left', 0) == 1 else 0,
                occupancy_info.get('name', 'unknown')
            ))
            inserted_count += 1
        
        conn.commit()
        logging.info(f"Inserted {inserted_count} departures, skipped {skipped_count}")
        
        # =====================
        # STEP 6: Log the fetch operation
        # =====================
        cursor.execute("""
            INSERT INTO fetch_logs (station_id, fetched_at, record_count, success)
            VALUES (%s, GETUTCDATE(), %s, 1)
        """, (station_id, inserted_count))
        conn.commit()
        
        # Clean up
        cursor.close()
        conn.close()
        
        # =====================
        # STEP 7: Return success response
        # =====================
        result = {
            "status": "success",
            "station": station,
            "station_id": station_id,
            "departures_fetched": len(departures),
            "departures_inserted": inserted_count,
            "departures_skipped": skipped_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return func.HttpResponse(
            json.dumps(result, indent=2),
            mimetype="application/json",
            status_code=200
        )
    
    except requests.exceptions.Timeout:
        logging.error("iRail API timeout")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "iRail API timeout"}),
            mimetype="application/json",
            status_code=504
        )
    
    except requests.exceptions.RequestException as e:
        logging.error(f"iRail API error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"iRail API error: {str(e)}"}),
            mimetype="application/json",
            status_code=502
        )
    
    except pymssql.Error as e:
        logging.error(f"Database error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"Database error: {str(e)}"}),
            mimetype="application/json",
            status_code=500
        )
    
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"Unexpected error: {str(e)}"}),
            mimetype="application/json",
            status_code=500
        )
