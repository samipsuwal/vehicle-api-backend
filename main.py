from http.client import HTTPException
from databases import Database
from fastapi import FastAPI
import services
database = Database("sqlite:///test.db")

app = FastAPI()


@app.on_event("startup")
async def database_connect():
    await database.connect()

@app.on_event("shutdown")
async def database_disconnect():
    await database.disconnect()


#Database layer
#subject to sql injection
async def get_cached_vehicle_by_VIN(vin):
    query="SELECT * FROM VEHICLES WHERE VIN='{}';".format(vin)
    vehicle_from_database = await database.fetch_one(query= query)
    #vehicle_from_database["CachedResult"] = True #do we want to save this in database? 
    return vehicle_from_database

async def insert_vehicle_into_database(vehicle):
    query="INSERT into VEHICLES (VIN, MAKE, MODEL, MODELYEAR, BODYCLASS)  VALUES ( '" + vehicle.VIN +"', '"+ vehicle.Make+"', '" + vehicle.Model+"', '" + vehicle.ModelYear+"', '" + vehicle.BodyClass + "');"
    result = await database.execute(query= query)
    return result

async def remove_vehicle_from_database(vin):
    query="DELETE FROM VEHICLES WHERE VIN ='{}';".format(vin)
    await database.execute(query=query)

async def get_all_vehicles_from_database():
    query = "SELECT VIN FROM VEHICLES"
    result = await database.fetch_all(query=query)
    return result

##END of Database Layer
    

#Beginning of routes

#API that returns VIN either from Cache or Client
#params-VIN
#return JSON response
@app.get("/lookup/{vin}")
async def lookup(vin: str):
    #TODO make sure the VIN is valid 17 alpha numeric
    if services.validate_vin(vin) is False:
        return "Invalid VIN: {}".format(vin)


    #get the vehicle from the database, service layer -> database layer
    cached_vehicle = await get_cached_vehicle_by_VIN(vin)

    if cached_vehicle is not None:
        #Work around #1:cannot add cached_result attribute to what is returned by the database
        return {"vin": cached_vehicle.VIN, "Make": cached_vehicle.Make, "Model":cached_vehicle.Model, "ModelYear": cached_vehicle.ModelYear, "BodyClass":cached_vehicle.BodyClass, "CachedResult":True}
    
    #vic wasn't found in the database or forced key was used
    requested_vehicle_from_client = await services.get_vehicle_from_client(vin)

    #the service should call database layer. 
    ##this doesn't has to be a blocking call, we can send the request back to the user, while asynchronously updating the database
    await insert_vehicle_into_database(requested_vehicle_from_client)
    
    return requested_vehicle_from_client



#API that removes entry from the Cache
#params: vin
#return success we are not going to send more specific message for security
@app.get("/remove/{vin}")
async def remove(vin: str):
    if services.validate_vin(vin) is False:
        return "Invalid VIN: {}".format(vin)

    await remove_vehicle_from_database(vin)
    return {"vin":vin, "cache_delete": "success"}


#Export the SQLLite cache in Parquet format
@app.get("/export")
async def export():
    all_vehicles = await get_all_vehicles_from_database() 
    data_parquet_format = services.convert_json_to_par(all_vehicles)

    return data_parquet_format


#End of routes