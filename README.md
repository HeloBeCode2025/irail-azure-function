# 🚆 iRail Azure Function - Live Departure Board

An Azure Function that fetches real-time Belgian train departure data from the [iRail API](https://docs.irail.be/) and stores it in Azure SQL Database.

## 📋 Project Overview

This is part of the BeCode Azure Challenge - a learning project to build a cloud-native data pipeline using Microsoft Azure.

### Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  iRail API  │ ──►  │  Azure Function  │ ──►  │  Azure SQL DB   │
│ /liveboard  │      │  (Python)        │      │  departures     │
└─────────────┘      └──────────────────┘      └─────────────────┘
```

## 🚀 Setup Instructions

### Prerequisites

1. Azure account with student subscription
2. Azure SQL Database (see database setup below)
3. GitHub account

### Database Setup

Run this SQL in your Azure SQL Database:

```sql
-- Create stations table
CREATE TABLE stations (
    station_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    standard_name VARCHAR(100),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6)
);

-- Create departures table
CREATE TABLE departures (
    id INT IDENTITY(1,1) PRIMARY KEY,
    departure_id VARCHAR(150) UNIQUE,
    station_id VARCHAR(20) NOT NULL,
    destination_id VARCHAR(20),
    destination_name VARCHAR(100),
    scheduled_time DATETIME NOT NULL,
    delay_seconds INT DEFAULT 0,
    platform VARCHAR(10),
    vehicle_id VARCHAR(50),
    vehicle_short VARCHAR(20),
    is_canceled BIT DEFAULT 0,
    has_left BIT DEFAULT 0,
    occupancy VARCHAR(20),
    fetched_at DATETIME DEFAULT GETUTCDATE(),
    FOREIGN KEY (station_id) REFERENCES stations(station_id)
);

-- Create fetch logs table
CREATE TABLE fetch_logs (
    id INT IDENTITY(1,1) PRIMARY KEY,
    station_id VARCHAR(20),
    fetched_at DATETIME DEFAULT GETUTCDATE(),
    record_count INT,
    success BIT,
    error_message VARCHAR(500)
);

-- Create indexes for performance
CREATE INDEX idx_departures_station_time 
ON departures(station_id, scheduled_time);

CREATE INDEX idx_departures_fetched 
ON departures(fetched_at);
```

### Function App Configuration

Add these environment variables in your Azure Function App:

| Name | Description |
|------|-------------|
| `SQL_SERVER` | Your Azure SQL server (e.g., `yourserver.database.windows.net`) |
| `SQL_DATABASE` | Database name (e.g., `irail-departures`) |
| `SQL_USERNAME` | SQL admin username |
| `SQL_PASSWORD` | SQL admin password |

### Deploying via GitHub

1. Fork or clone this repository
2. In Azure Portal, go to your Function App
3. Navigate to **Deployment Center**
4. Select **GitHub** as source
5. Authorize and select this repository
6. Azure will automatically deploy on push

## 📡 API Usage

### Endpoint

```
GET https://your-function-app.azurewebsites.net/api/fetch_departures?station=Brussels-South
```

### Query Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `station` | No | `Brussels-South` | Name of the Belgian train station |

### Example Stations

- `Brussels-South` (Bruxelles-Midi)
- `Brussels-Central`
- `Antwerp-Central`
- `Ghent-Sint-Pieters`
- `Liege-Guillemins`
- `Leuven`
- `Bruges`

### Response

```json
{
  "status": "success",
  "station": "Brussels-South",
  "station_id": "BE.NMBS.008814001",
  "departures_fetched": 32,
  "departures_inserted": 28,
  "departures_skipped": 4,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 📁 Project Structure

```
irail-azure-function/
├── fetch_departures/
│   ├── __init__.py          # Main function code
│   └── function.json        # Function bindings configuration
├── host.json                 # Function app host configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## 🔧 Local Development

1. Install [Azure Functions Core Tools](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)
2. Create a `local.settings.json` file:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "SQL_SERVER": "your-server.database.windows.net",
    "SQL_DATABASE": "irail-departures",
    "SQL_USERNAME": "your-username",
    "SQL_PASSWORD": "your-password"
  }
}
```

3. Run `func start` to test locally

## 📚 Resources

- [iRail API Documentation](https://docs.irail.be/)
- [Azure Functions Python Guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure SQL Database](https://docs.microsoft.com/en-us/azure/azure-sql/)

## 📝 License

This project is for educational purposes as part of the BeCode training program.
