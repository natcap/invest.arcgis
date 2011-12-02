# Marine InVEST: Coastal Protection (Profile Generator)
# Authors: Greg Guannel, Gregg Verutes
# 12/01/11

# import libraries
import numpy as num
import CPf_SignalSmooth as SignalSmooth
import string,sys,os,time,datetime,shlex
import fpformat,operator
import arcgisscripting
import shutil

from win32com.client import Dispatch
from scipy.interpolate import interp1d
from scipy import optimize
from math import *
from matplotlib import *
from pylab import *

# create the geoprocessor object
gp=arcgisscripting.create()
gp.AddMessage("\nChecking and preparing inputs...")

# set output handling
gp.OverwriteOutput=1
# check out any necessary extensions
gp.CheckOutExtension("management")
gp.CheckOutExtension("analysis")
gp.CheckOutExtension("conversion")
gp.CheckOutExtension("spatial")

# error messages
msgArguments="Problem with arguments."

try:
    # get parameters
    parameters=[]
    now=datetime.datetime.now()
    parameters.append("Date and Time: "+now.strftime("%Y-%m-%d %H:%M"))
    gp.workspace=gp.GetParameterAsText(0)
    parameters.append("Workspace: "+gp.workspace)
    subwsStr=gp.GetParameterAsText(1)
    parameters.append("Label for Profile Generator Run (10 characters max): "+subwsStr)
    LandPoint=gp.GetParameterAsText(2)
    parameters.append("Land Point: "+LandPoint)
    LandPoly=gp.GetParameterAsText(3)
    parameters.append("Land Polygon: "+LandPoly)
    InputTable=gp.GetParameterAsText(4)
    parameters.append("Profile Generator Excel Table: "+InputTable)
    ProfileQuestion=gp.GetParameterAsText(5)
    parameters.append("Do you have a nearshore bathymetry GIS layer?: "+ProfileQuestion)
    BathyGrid=gp.GetParameterAsText(6)
    parameters.append("IF 1: Bathymetric Grid (DEM): "+BathyGrid)
    HabDirectory=gp.GetParameterAsText(7)
    parameters.append("IF 1: Habitat Data Directory: "+HabDirectory)
    BufferDist=gp.GetParameterAsText(8)
    parameters.append("IF 1: Land Point Buffer Distance: "+BufferDist)
    CSProfile=gp.GetParameterAsText(9)
    parameters.append("IF 2: Upload Your Cross-Shore Profile: "+CSProfile)
    SmoothParameter=float(gp.GetParameterAsText(10))
    parameters.append("Smoothing Percentage (Value of '0' means no smoothing): "+str(SmoothParameter))
    WW3_Pts=gp.GetParameterAsText(11)
    parameters.append("Wave Watch 3 Model Data: "+WW3_Pts)
    FetchQuestion=gp.GetParameterAsText(12)
    parameters.append("Do you wish to calculate fetch for LandPoint?: "+FetchQuestion)

except:
    raise Exception,msgArguments+gp.GetMessages(2)


#CREATE DIRECTORIES AND VARIABLES###################################################################
# remove spaces and shorten 'subwsStr' if greater than 10 characters
subwsStr=subwsStr.replace(" ","")
subwsStr=subwsStr[0:10]

# intermediate and output directories
interws=gp.GetParameterAsText(0)+os.sep+"scratch"+os.sep
outputws=gp.GetParameterAsText(0)+os.sep+"_ProfileGenerator_Outputs"+os.sep
subws=outputws+subwsStr+os.sep
maps=subws+"maps"+os.sep
html_txt=subws+"html_txt"+os.sep

try:
    thefolders=["scratch","_ProfileGenerator_Outputs"]
    for folder in thefolders:
        if not gp.exists(gp.workspace+folder):
            gp.CreateFolder_management(gp.workspace,folder)

    thefolders=[subwsStr]
    for folder in thefolders:
        if not gp.exists(outputws+folder):
            gp.CreateFolder_management(outputws,folder)  

    thefolders=["maps","html_txt"]
    for folder in thefolders:
        if not gp.exists(subws+folder):
            gp.CreateFolder_management(subws,folder)  
except:
    raise Exception,"Error creating folders"

LandPointLyr=interws+"LandPointLyr.lyr"
LandPolyLyr=interws+"LandPolyLyr.lyr"
PT1=interws+"PT1.shp"
PT2=interws+"PT2.shp"
PT1_Z=interws+"PT1_Z.shp"
PT2_Z=interws+"PT2_Z.shp"
PT_Z_Near=interws+"PT_Z_Near.shp"
Backshore_Pts=interws+"Backshore_Pts.shp"
Profile_Pts_Merge=interws+"Profile_Pts_Merge.shp"
Profile_Pts_Lyr=interws+"Profile_Pts_Lyr.lyr"
LandPoint_Buff=interws+"LandPoint_Buff.shp"
LandPoint_Buff50k=interws+"LandPoint_Buff50k.shp"
LandPoint_Geo=interws+"LandPoint_Geo.shp"
Shoreline=interws+"Shoreline.shp"
Shoreline_Buff_Clip=interws+"Shoreline_Buff_Clip.shp"
Shoreline_Buff_Clip_Diss=interws+"Shoreline_Buff_Clip_Diss.shp"
PtsCopy=interws+"PtsCopy.shp"
PtsCopy2=interws+"PtsCopy2.shp"
PtsCopyLR=interws+"PtsCopy2_lineRotate.shp"
PtsCopy3=interws+"PtsCopy3.shp"
PtsCopyLD=interws+"PtsCopy3_lineDist.shp"
Fetch_AOI=interws+"Fetch_AOI.shp"
UnionFC=interws+"UnionFC.shp"
SeaPoly=interws+"SeaPoly.shp"
seapoly_rst=interws+"seapoly_rst"
seapoly_e=interws+"seapoly_e"
PtsCopyEL=interws+"PtsCopy2_eraseLand.shp"
PtsCopyExp=interws+"PtsCopy2_explode.shp"
PtsCopyExp_Lyr=interws+"PtsCopy2_explode.lyr"
WW3_Pts_prj=interws+"WW3_Pts_prj.shp"
costa_ww3=interws+"costa_ww3"
LandPoint_WW3=interws+"LandPoint_WW3.shp"

BathyProfile=html_txt+"BathyProfile_"+subwsStr+".txt"
CreatedProfile=html_txt+"CreatedProfile_"+subwsStr+".txt"
ProfileCutGIS=html_txt+"ProfileCutGIS_"+ subwsStr+".txt"
HabitatLocation=html_txt+"HabitatLocation_"+ subwsStr+".txt"
Profile_HTML=html_txt+"profile.html"
FetchWindWave_HTML=html_txt+"fetchwindwave.html"
Wind_Plot=html_txt+"Wind_Plot.png"
Fetch_Plot=html_txt+"Fetch_Plot.png"

Profile_Pts=maps+"Profile_Pts.shp"
Profile_Pts_Hab=maps+"Profile_Pts_Hab.shp"
Fetch_Vectors=maps+"Fetch_Vectors.shp"
Fetch_Distances=maps+"Fetch_Distances.shp"
UploadedProfile=maps+"UploadedProfile.shp"

# VARIOUS FUNCTIONS #####################################################################
def AddField(FileName,FieldName,Type,Precision,Scale):
    fields=gp.ListFields(FileName,FieldName)
    field_found=fields.Next()
    if field_found:
        gp.DeleteField_management(FileName,FieldName)
    gp.AddField_management(FileName,FieldName,Type,Precision,Scale,"","","NON_NULLABLE","NON_REQUIRED","")
    return FileName

def getDatum(thedata):
    desc=gp.describe(thedata)
    SR=desc.SpatialReference
    if SR.Type=="Geographic":
        strDatum=SR.DatumName         
    else:
        gp.OutputCoordinateSystem=SR
        strSR=str(gp.OutputCoordinateSystem)
        gp.OutputCoordinateSystem=""
        n1=strSR.find("GEOGCS")
        n2=strSR.find("PROJECTION")
        strDatum=strSR[n1:n2-1]
    return strDatum

def ckDatum(thedata):
    desc=gp.describe(thedata)
    SR=desc.SpatialReference
    if SR.Type=="Geographic":
        strDatum=SR.DatumName         
    else:
        gp.OutputCoordinateSystem=SR
        strSR=str(gp.OutputCoordinateSystem)
        gp.OutputCoordinateSystem=""
        n1=strSR.find("DATUM[\'")
        n2=strSR.find("\'",n1+7)
        strDatum=strSR[n1+7:n2]
    if strDatum=="D_WGS_1984":
        pass
    else:
        gp.AddError(thedata+" is not a valid input.\nThe model requires data inputs and a projection with the \"WGS84\" datum.\nSee InVEST FAQ document for how to reproject datasets.")
        raise Exception

def ckProjection(data):
    dataDesc=gp.describe(data)
    spatreflc=dataDesc.SpatialReference
    if spatreflc.Type <> 'Projected':
        gp.AddError(data+" does not appear to be projected.  It is assumed to be in meters.")
        raise Exception
    if spatreflc.LinearUnitName <> 'Meter':
        gp.AddError("This model assumes that "+data+" is projected in meters for area calculations.  You may get erroneous results.")
        raise Exception

def checkGeometry(thedata,Type,Message):
    if gp.Describe(thedata).ShapeType <> Type:
        raise Exception,"\nInvalid input: "+thedata+"\n"+Message+" must be of geometry type "+Type+"."

def checkInteger(thedata):
    if thedata.find("0")==-1 and thedata.find("1")==-1 and thedata.find("2")==-1 and thedata.find("3")==-1 and thedata.find("4")==-1 and thedata.find("5")==-1 and thedata.find("6")==-1 and thedata.find("7")==-1 and thedata.find("8")==-1 and thedata.find("9")==-1:
        gp.AddError(thedata +" must contain an underscore followed by an integer ID at the end of it's name (e.g. filename_1.shp). This is necessary to properly link it with the input table.")
        raise Exception

def grabProjection(data):
    dataDesc=gp.describe(data)
    sr=dataDesc.SpatialReference
    gp.OutputCoordinateSystem=sr
    strSR=str(gp.OutputCoordinateSystem)
    return strSR

def PTCreate(PTType,midx,midy,TransectDist): # function to create point transects
    if PTType==1:
        y1=midy+TransectDist
        y2=midy-TransectDist
        x1=midx
        x2=midx
    elif PTType==2:
        y1=midy
        y2=midy 
        x1=midx+TransectDist
        x2=midx-TransectDist
    elif PTType==3:
        y1=NegRecip*(TransectDist)+midy
        y2=NegRecip*(-TransectDist)+midy
        x1=midx+TransectDist
        x2=midx-TransectDist
    elif PTType==4:
        y1=midy+TransectDist
        y2=midy-TransectDist
        x1=(TransectDist/NegRecip)+midx
        x2=(-TransectDist/NegRecip)+midx
    elif PTType==5:
        y1=midy+TransectDist
        y2=midy-TransectDist
        x1=(TransectDist/NegRecip)+midx
        x2=(-TransectDist/NegRecip)+midx
    elif PTType==6:
        y1=NegRecip*(TransectDist)+midy
        y2=NegRecip*(-TransectDist)+midy
        x1=midx+TransectDist
        x2=midx-TransectDist
    return x1,y1,x2,y2

def compareProjections(LandPoint,LandPoly):
    if gp.describe(LandPoint).SpatialReference.name <> gp.describe(LandPoly).SpatialReference.name:
        gp.AddError("Projection Error: "+LandPoint+" is in a different projection from the LandPoly data.  The two inputs must be the same projection to calculate depth profile.")
        raise Exception

def Indexed(x,value): # locates index of point in vector x that has closest value as variable value
    mylist=abs(x-value)    
    if isinstance(x,num.ndarray):
        mylist=mylist.tolist()
    minval=min(mylist)
    ind=[i for i,v in enumerate(mylist) if v==minval]
    ind=ind[0]
    return ind

def SlopeModif(X,Y,SlopeMod,OffMod,ShoreMod): # replaces/adds linear portion to profile
    if SlopeMod <> 0:
        m=1.0/SlopeMod # slope
    else:
        m=0.0
        
    Xend=X[-1] # last point in profile
    if ShoreMod < Xend: # if modified portion in within profile
        of=Indexed(X,OffMod) # locate offshore point
        sho=Indexed(X,ShoreMod) # locate shoreward point
            
        # modify the slope between offshore and shoreward points
        Y[of:sho]=m*X[of:sho]+Y[of]-m*X[of]
    else:
        of=Indexed(X,OffMod) # locate offshore point
        dist=ShoreMod-OffMod
        temp_x=num.arange(0,int(dist),1) # length of the segment modified/added
        out=num.arange(Indexed(temp_x,dist)+1,len(temp_x),1) # remove points that are beyond shoreward limit 
        temp_y=m*temp_x+Y[of];temp_y=num.delete(temp_y,out,None) # new profile
        Y=num.append(Y[0:of-1],temp_y,None); # append depth vector
        X=num.append(X[0:of-1],temp_x+X[of],None) # append X vector

        # resample on vector with dx=1
        F=interp1d(X,Y);X=num.arange(X[0],X[-1],1)
        Y=F(X);X=X-X[0]

        # remove NaNs        
        temp=numpy.isnan(Y).any()
        if str(temp)=="True":
            keep=X*0+(-1)
            for xx in range(len(Y)):
                if str(numpy.isnan(Y[xx]))=="False":
                    keep[xx]=xx
            keep=num.nonzero(keep > 0);keep=keep[0]
            Y=Y[keep];X=X[keep]
    return X,Y

def DataRemove(X,Y,OffDel,ShoreDel): # remove date from transect 
    of=Indexed(Xmod,OffDel);sho=Indexed(Xmod,ShoreDel)# locate offshore and shoreward points
    out=num.arange(of,sho+1,1)
    Y=num.delete(Y,out,None) # remove points from Ymod
    X=num.delete(X,out,None) # remove points from Xmod
    # resample on vector with dx=1
    F=interp1d(X,Y);X=num.arange(X[0],X[-1],1)
    Y=F(X);X=X-X[0]
    return X,Y

# wind-wave generation
def WindWave(U,F,d):
    ds=g*d/U**2.0;Fs=g*F/U**2.0
    A=tanh(0.343*ds**1.14)
    B=tanh(4.14e-4*Fs**0.79/A)
    H=0.24*U**2/g*(A*B)**0.572 # wave height
    A=tanh(0.1*ds**2.01)
    B=tanh(2.77e-7*Fs**1.45/A)
    T=7.69*U/g*(A*B)**0.18 # wave period
    return H,T

# VARIOUS CHECKS BEFORE WE RUN TOOL###############################################################
# variables (hard-coded)
SampInterval=1
TransectDist=0
BearingsNum=16
RadLineDist=50000

# check that correct inputs were provided based on 'ProfileQuestion'
if ProfileQuestion=="(1) Yes":
    if not BathyGrid:
        gp.AddError("A bathymetry grid input is required to create a point transect.")
        raise Exception
    if not HabDirectory:
        gp.AddError("A habitat data directory input is required to create a point transect.")
        raise Exception

elif ProfileQuestion=="(2) No,but I will upload a cross-shore profile":
    if not CSProfile:
        gp.AddError("A cross-shore profile input is required.")
        raise Exception

ckDatum(LandPoint) # check that datum is WGS84

# limit buffer distance
if int(BufferDist) > 500 or int(BufferDist) < 40:
    gp.AddError("Buffer distance for 'Land Point' must be greater than 40 and less than 500 meters.")
    raise Exception

# check that 'LandPoint' is within 150 meters of coastline
if ProfileQuestion=="(1) Yes":
    gp.MakeFeatureLayer_management(LandPoint,LandPointLyr,"","","")
    gp.MakeFeatureLayer_management(LandPoly,LandPolyLyr,"","","")
    PointSelect=gp.SelectLayerByLocation_management(LandPointLyr,"WITHIN_A_DISTANCE",LandPolyLyr,str(int(BufferDist)+150)+" Meters","NEW_SELECTION")
    if gp.GetCount_management(PointSelect)==0:
        gp.AddError("Shoreline was not found within "+str(BufferDist)+" meters of 'Land Point' input.\nEither increase the buffer distance or move the 'LandPoint' input closer to the coastline.")
        raise Exception

# check that three inputs are projected
ckProjection(LandPoint)
ckProjection(LandPoly)
if BathyGrid:
    ckProjection(BathyGrid)
geo_projection=getDatum(LandPoint) # get datum of 'Land Point'

# check that smoothing input is within proper range
if SmoothParameter < 0.0 or SmoothParameter > 100.0:
    gp.AddError("Smoothing parameter value must be between 0 and 100.  Please modify your input and run the tool again.")
    raise Exception

# angle direction list for fetch and WW3
dirList=[0,22,45,67,90,112,135,157,180,202,225,247,270,292,315,337]

# modal wave height in case user doesn't enter....
Hm=-1;Tm=-1

# buffer 'LandPoint' by 50km
gp.Buffer_analysis(LandPoint,LandPoint_Buff50k,"50000 Meters","FULL","ROUND","NONE","")
# convert buffered 'LandPoint' into bathy polygon
gp.Extent=LandPoint_Buff50k
# grab projection spatial reference from 'Land Poly' input
dataDesc=gp.describe(LandPoly)
spatialRef=dataDesc.SpatialReference
gp.CreateFeatureClass_management(interws,"Fetch_AOI.shp","POLYGON","#","#","#",spatialRef)
# grab four corners from 'PtsCopyLR'
CoordList=shlex.split(gp.Extent)

# when creating a polygon,the coordinates for the starting point must be the same as the coordinates for the ending point
cur=gp.InsertCursor(Fetch_AOI)
row=cur.NewRow()
PolygonArray=gp.CreateObject("Array")
pnt=gp.CreateObject("Point")
pnt.x=float(CoordList[0])
pnt.y=float(CoordList[1])
PolygonArray.add(pnt)
pnt.x=float(CoordList[0])
pnt.y=float(CoordList[3])
PolygonArray.add(pnt)
pnt.x=float(CoordList[2])
pnt.y=float(CoordList[3])
PolygonArray.add(pnt)
pnt.x=float(CoordList[2])
pnt.y=float(CoordList[1])
PolygonArray.add(pnt)
pnt.x=float(CoordList[0])
pnt.y=float(CoordList[1])
PolygonArray.add(pnt)
row.shape=PolygonArray
cur.InsertRow(row)
del row,cur

# WW3,FETCH AND AOI CALCULATIONS###################################################################
if WW3_Pts or FetchQuestion=='(1) Yes':
    gp.AddMessage("\nPreparing inputs for Wave Watch III and/or fetch calculations...")
    # erase from 'Fetch_AOI' areas where there is land
    LandPoly=AddField(LandPoly,"ERASE","SHORT","0","0")
    gp.CalculateField_management(LandPoly,"ERASE","1","VB")
    UnionExpr=Fetch_AOI+" 1; "+LandPoly+" 2"        
    gp.Union_analysis(UnionExpr,UnionFC)

    # select features where "ERASE=0"
    gp.Select_analysis(UnionFC,SeaPoly,"\"ERASE\"=0")

# read WW3 Info
if WW3_Pts:
    gp.AddMessage("...reading Wave Watch III information")
    # create cost surface based on 'SeaPoly'
    gp.Extent=Fetch_AOI
    projection=grabProjection(LandPoint)
    gp.Project_management(WW3_Pts,WW3_Pts_prj,projection)
    SeaPoly=AddField(SeaPoly,"SEA","SHORT","","")
    gp.CalculateField_management(SeaPoly,"SEA","1","PYTHON","")
    gp.FeatureToRaster_conversion(SeaPoly,"SEA",seapoly_rst,"250")
    gp.Expand_sa(seapoly_rst,seapoly_e,"1","1")
    # allocate 'WW3_Pts' throughout cost surface
    gp.CostAllocation_sa(WW3_Pts_prj,seapoly_e,costa_ww3,"","","FID","","")
    # determine which point is closest to 'LandPoint'
    gp.ExtractValuesToPoints_sa(LandPoint,costa_ww3,LandPoint_WW3,"NONE")
    cur=gp.UpdateCursor(LandPoint_WW3)
    row=cur.Next()
    WW3_FID=row.GetValue("RASTERVALU")
    del row
    del cur

    # populate list with data from closest WW3 point
    WW3_ValuesList=[]
    SrchCondition="FID="+str(WW3_FID)
    cur=gp.SearchCursor(WW3_Pts_prj,SrchCondition,"","")
    row=cur.Next()
    WW3_ValuesList.append(row.GetValue("LAT")) # 0
    WW3_ValuesList.append(row.GetValue("LONG")) # 1
    for i in range(0,len(dirList)):
        WW3_ValuesList.append(row.GetValue("V10PCT_"+str(dirList[i]))) # 2-17
    for i in range(0,len(dirList)):
        WW3_ValuesList.append(row.GetValue("V25PCT_"+str(dirList[i]))) # 18-33
    for i in range(0,len(dirList)):
        WW3_ValuesList.append(row.GetValue("V_MAX_"+str(dirList[i]))) # 34-49
    WW3_ValuesList.append(row.GetValue("V_10YR")) # 50
    WW3_ValuesList.append(row.GetValue("H_10PCT")) # 51
    WW3_ValuesList.append(row.GetValue("T_10PCT")) # 52
    WW3_ValuesList.append(row.GetValue("H_25PCT")) # 53
    WW3_ValuesList.append(row.GetValue("T_25PCT")) # 54
    WW3_ValuesList.append(row.GetValue("H_MAX")) # 55
    WW3_ValuesList.append(row.GetValue("T_MAX")) # 56
    WW3_ValuesList.append(row.GetValue("H_10YR")) # 57
    WW3_ValuesList.append(row.GetValue("He")) # 58
    WW3_ValuesList.append(row.GetValue("Hmod")) # 59
    WW3_ValuesList.append(row.GetValue("Tmod")) # 60
    del row,cur

    # maximum wave height
    WavMax=[0,0];WavMax[0]=WW3_ValuesList[55];WavMax[1]=WW3_ValuesList[56]
    # top 10% wave height
    Wav10=[0,0];Wav10[0]=WW3_ValuesList[51];Wav10[1]=WW3_ValuesList[52]
    # top 25% wave height
    Wav25=[0,0];Wav25[0]=WW3_ValuesList[53];Wav25[1]=WW3_ValuesList[54]
    # 10-yr wave height
    Wav10yr=WW3_ValuesList[57]
    # maximum wind speed
    WiMax=num.arange(0,16,1)*0      
    for ii in range(0,16):
        WiMax[ii]=WW3_ValuesList[ii+34]
    # top 10% wind speed
    Wi10=num.arange(0,16,1)*0       
    for ii in range(0,16):
        Wi10[ii]=WW3_ValuesList[ii+2]
    # top 25% wind speed
    Wi25=num.arange(0,16,1)*0       
    for ii in range(0,16):
        Wi25[ii]=WW3_ValuesList[ii+18]
    # Hmod and Tmod 
    Hm=WW3_ValuesList[59]
    Tm=WW3_ValuesList[60]

# compute fetch
if FetchQuestion=='(1) Yes':
    # create fetch vectors
    gp.AddMessage("...creating fetch vectors")

    # radials function
    def Radials(PtsName,Suffix):
        fc=string.replace(PtsName,"\\","/")
        descfc=gp.describe(fc)
        sr=descfc.spatialreference
        # process the feature class attributes
        lstfc=string.split(fc,"/")
        for fl in lstfc:
            fn=fl
        strWorkspace=string.replace(fc,fl,"")
        gp.workspace=strWorkspace
        newfn=string.replace(fl,".shp",Suffix)
        # check for existence
        if gp.exists(strWorkspace+newfn):
            gp.delete_management(strWorkspace+newfn)
            gp.refreshcatalog(gp.workspace)
        # create the fc
        gp.CreateFeatureClass_management(gp.workspace,newfn,"POLYLINE",fc,"SAME_AS_TEMPLATE","SAME_AS_TEMPLATE",sr)
        addrecs=gp.insertcursor(strWorkspace+newfn)
        gp.refreshcatalog(gp.workspace)
          
        recs=gp.SearchCursor(fc)
        rec=recs.next()
        lstFields=gp.listfields(fc)
        while rec:
            # get the angle
            rotation=rec.getvalue("BEARING")
            length=rec.getvalue("DISTANCE")
            bearing=math.radians(rotation)
            angle=math.radians((360-math.degrees(bearing))+90)        
            # get the feature and compute the to point
            pt=rec.shape.getpart(0)
            x=operator.add(math.cos(angle)*length,pt.x)
            y=operator.add(math.sin(angle)*length,pt.y)
            # build up the record
            addrec=addrecs.newrow()    
            # create the shape
            newArray=gp.createobject("array")
            newArray.add (pt)
            newPt=gp.createobject("point")
            newPt.x=x
            newPt.y=y
            newArray.add(newPt)
            # maintain the attributes
            lstFields.reset()
            fld=lstFields.next()
            while fld:
                if fld.name <> "FID" and fld.name <> "OBJECTID" and fld.name <> "SHAPE":
                    addrec.SetValue(fld.name,rec.GetValue(fld.name))
                fld=lstFields.next()
            # add shape
            addrec.shape=newArray
            addrecs.insertrow(addrec)
            rec=recs.next()
        del rec,recs    
    
    # copy original point twice and add fields to second copy
    gp.CopyFeatures_management(LandPoint,PtsCopy,"","0","0","0")
    gp.CopyFeatures_management(LandPoint,PtsCopy2,"","0","0","0")
    gp.CopyFeatures_management(LandPoint,PtsCopy3,"","0","0","0")
    PtsCopy2=AddField(PtsCopy2,"DISTANCE","SHORT","8","")
    PtsCopy2=AddField(PtsCopy2,"BEARING","DOUBLE","","")
    PtsCopy2=AddField(PtsCopy2,"BISECTANG","DOUBLE","","")

    CopyExpr=PtsCopy
    for i in range(0,(BearingsNum*9)-2):
        CopyExpr=CopyExpr+";"+PtsCopy

    BiSectAngFullList=[]
    BiSectAngList=[1.0,0.999048,0.996195,0.991445,0.984808,0.984808,0.991445,0.996195,0.999048]

    for i in range(0,16):
        for j in range(0,len(BiSectAngList)):

            BiSectAngFullList.append(BiSectAngList[j])
        
    gp.Append_management(CopyExpr,PtsCopy2,"NO_TEST","","")
    gp.CalculateField_management(PtsCopy2,"DISTANCE",str(RadLineDist),"PYTHON","")

    # translate information from list into perp transect attribute table
    cur=gp.UpdateCursor(PtsCopy2,"","","BEARING; FID; BISECTANG")
    row=cur.Next()
    m=0
    while row:
        FID=float(row.GetValue("FID"))
        Bearing=float((360.000/((BearingsNum*8.0)+BearingsNum))*FID)
        row.SetValue("Bearing",Bearing)
        row.SetValue("BiSectAng",BiSectAngFullList[m])
        m=m+1
        cur.UpdateRow(row)
        row=cur.Next()
    del cur,row

    # create radials
    Radials(PtsCopy2,"_lineRotate.shp")

    # erase parts of line where it overlaps land (works for ArcView)
    gp.Intersect_analysis(PtsCopyLR+" 1;"+SeaPoly+" 2",PtsCopyEL,"ALL","","INPUT")
    gp.MultipartToSinglepart_management(PtsCopyEL,PtsCopyExp)
    # convert to layer to select only lines originating from point source
    gp.MakeFeatureLayer_management(PtsCopyExp,PtsCopyExp_Lyr,"",gp.workspace,"")
    gp.SelectLayerByLocation_management(PtsCopyExp_Lyr,"WITHIN_A_DISTANCE",LandPoint,"20 Meters","NEW_SELECTION")
    gp.CopyFeatures_management(PtsCopyExp_Lyr,Fetch_Vectors,"","0","0","0")
    # add and calculate "LENGTH_M" field
    Fetch_Vectors=AddField(Fetch_Vectors,"LENGTH_M","LONG","6","")
    gp.CalculateField_management(Fetch_Vectors,"LENGTH_M","!shape.length@meters!","PYTHON","")

    # populate fetch distances to a list
    AngleList=[0.0,22.5,45.0,67.5,90.0,112.5,135.0,157.5,180.0,202.5,225.0,247.5,270.0,292.5,315.0,337.5]
    FetchList=[0.0]*16
    # translate information from list into perp transect attribute table
    cur=gp.UpdateCursor(Fetch_Vectors,"","","BEARING; LENGTH_M")
    row=cur.Next()
    while row:
        Angle=float(row.GetValue("BEARING"))
        if Angle in AngleList:
            indexAngle=AngleList.index(Angle)
            FetchList[indexAngle]=float(row.GetValue("LENGTH_M"))
        row=cur.Next()
    del cur,row

    binD1=[]; binBiAng1=[]; binD2=[]; binBiAng2=[]; binD3=[]; binBiAng3=[]; binD4=[]; binBiAng4=[]
    binD5=[]; binBiAng5=[]; binD6=[]; binBiAng6=[]; binD7=[]; binBiAng7=[]; binD8=[]; binBiAng8=[]
    binD9=[]; binBiAng9=[]; binD10=[]; binBiAng10=[]; binD11=[]; binBiAng11=[]; binD12=[]; binBiAng12=[]
    binD13=[]; binBiAng13=[]; binD14=[]; binBiAng14=[]; binD15=[]; binBiAng15=[]; binD16=[]; binBiAng16=[]

    cur=gp.UpdateCursor(Fetch_Vectors,"","","BEARING; LENGTH_M; BISECTANG")
    row=cur.Next()    
    while row:
        Bearing=float(row.GetValue("BEARING"))
        if Bearing >= 350.0 and Bearing <= 10.0:
            binD1.append(row.GetValue("LENGTH_M"))
            binBiAng1.append(row.GetValue("BiSectAng"))
        elif Bearing >= 12.5 and Bearing <= 32.5:
            binD2.append(row.GetValue("LENGTH_M"))
            binBiAng2.append(row.GetValue("BiSectAng"))
        elif Bearing >= 35.0 and Bearing <= 55.0:
            binD3.append(row.GetValue("LENGTH_M"))
            binBiAng3.append(row.GetValue("BiSectAng"))
        elif Bearing >= 57.5 and Bearing <= 77.5:
            binD4.append(row.GetValue("LENGTH_M"))
            binBiAng4.append(row.GetValue("BiSectAng"))
        elif Bearing >= 80.0 and Bearing <= 100.0:
            binD5.append(row.GetValue("LENGTH_M"))
            binBiAng5.append(row.GetValue("BiSectAng"))
        elif Bearing >= 102.5 and Bearing <= 122.5:
            binD6.append(row.GetValue("LENGTH_M"))
            binBiAng6.append(row.GetValue("BiSectAng"))
        elif Bearing >= 125.0 and Bearing <= 145.0:
            binD7.append(row.GetValue("LENGTH_M"))
            binBiAng7.append(row.GetValue("BiSectAng"))
        elif Bearing >= 147.5 and Bearing <= 167.5:
            binD8.append(row.GetValue("LENGTH_M"))
            binBiAng8.append(row.GetValue("BiSectAng"))
        elif Bearing >= 170.0 and Bearing <= 190.0:
            binD9.append(row.GetValue("LENGTH_M"))
            binBiAng9.append(row.GetValue("BiSectAng"))
        elif Bearing >= 192.5 and Bearing <= 212.5:
            binD10.append(row.GetValue("LENGTH_M"))
            binBiAng10.append(row.GetValue("BiSectAng"))
        elif Bearing >= 215.0 and Bearing <= 235.0:
            binD11.append(row.GetValue("LENGTH_M"))
            binBiAng11.append(row.GetValue("BiSectAng"))
        elif Bearing >= 237.5 and Bearing <= 257.5:
            binD12.append(row.GetValue("LENGTH_M"))
            binBiAng12.append(row.GetValue("BiSectAng"))
        elif Bearing >= 260.0 and Bearing <= 280.0:
            binD13.append(row.GetValue("LENGTH_M"))
            binBiAng13.append(row.GetValue("BiSectAng"))
        elif Bearing >= 282.5 and Bearing <= 302.5:
            binD14.append(row.GetValue("LENGTH_M"))
            binBiAng14.append(row.GetValue("BiSectAng"))
        elif Bearing >= 305.0 and Bearing <= 325.0:
            binD15.append(row.GetValue("LENGTH_M"))
            binBiAng15.append(row.GetValue("BiSectAng"))
        elif Bearing >= 327.5 and Bearing <= 347.5:
            binD16.append(row.GetValue("LENGTH_M"))
            binBiAng16.append(row.GetValue("BiSectAng"))
        cur.UpdateRow(row)
        row=cur.Next()
    del row,cur
    
    # use 'FetchMean' function to summarize bins
    def FetchCalc(binD,binBiAng,index):
        if len(binD) > 0 and binD.count(0) < 3: # and binD has less than 3 zeros in it.
            numer=0.0
            denom=0.0
            for i in range(0,len(binD)):
                numer=numer+binD[i]*num.cos(binBiAng[i])
                denom=denom+num.cos(binBiAng[i])
            FetchList[index]=(numer/denom)
        return FetchList

    FetchList=num.zeros(16,dtype=num.float64)
    FetchCalc(binD4,binBiAng4,0); FetchCalc(binD3,binBiAng3,1); FetchCalc(binD2,binBiAng2,2); FetchCalc(binD1,binBiAng1,3)
    FetchCalc(binD16,binBiAng16,4); FetchCalc(binD15,binBiAng15,5); FetchCalc(binD14,binBiAng14,6); FetchCalc(binD13,binBiAng13,7)
    FetchCalc(binD12,binBiAng12,8); FetchCalc(binD11,binBiAng11,9); FetchCalc(binD10,binBiAng10,10); FetchCalc(binD9,binBiAng9,11)
    FetchCalc(binD8,binBiAng8,12); FetchCalc(binD7,binBiAng7,13); FetchCalc(binD6,binBiAng6,14); FetchCalc(binD5,binBiAng5,15)

    # save fetch distance values to print out in HTML
    FetchFinalList=[]
    for i in range(3,-1,-1):
        FetchFinalList.append(FetchList[i])
    for i in range(len(dirList)-1,3,-1):
        FetchFinalList.append(FetchList[i])

    # copy original point add fields to third copy
    gp.CopyFeatures_management(LandPoint,PtsCopy3,"","0","0","0")
    PtsCopy3=AddField(PtsCopy3,"DISTANCE","SHORT","8","")
    PtsCopy3=AddField(PtsCopy3,"BEARING","DOUBLE","","")

    CopyExpr=PtsCopy
    for i in range(0,14):
        CopyExpr=CopyExpr+";"+PtsCopy
    gp.Append_management(CopyExpr,PtsCopy3,"NO_TEST","","")

    # translate information from list into perp transect attribute table
    cur=gp.UpdateCursor(PtsCopy3,"","","BEARING; DISTANCE")
    row=cur.Next()
    m=0
    while row:
        row.SetValue("BEARING",AngleList[m])
        row.SetValue("DISTANCE",FetchFinalList[m])
        m=m+1
        cur.UpdateRow(row)
        row=cur.Next()
    del cur,row

    # create radials
    Radials(PtsCopy3,"_lineDist.shp")
    
    # select fetch lines where "DISTANCE > 0"
    gp.Select_analysis(PtsCopyLD,Fetch_Distances,"\"DISTANCE\" > 0")

# compute wave height from wind
if WW3_Pts and FetchQuestion=='(1) Yes':
    gp.AddMessage("...computing locally generated wind-wave characteristics from fetch")
    g=9.81;
    Fd=FetchFinalList;
    WiWavMax=16*[0.0];WiPerMax=16*[0.0]
    for ff in range(16): # compute wave height in each fetch direction
        if WiMax[ff] <> 0:
            WiWavMax[ff],WiPerMax[ff]=WindWave(WiMax[ff],Fd[ff],100)
    WiWav10=16*[0.0];WiPer10=16*[0.0]
    for ff in range(16): # compute wave height in each fetch direction
        if Wi10[ff] <> 0:
            WiWav10[ff],WiPer10[ff]=WindWave(Wi10[ff],Fd[ff],100)
    WiWav25=16*[0.0];WiPer25=16*[0.0]
    for ff in range(16): # compute wave height in each fetch direction
        if Wi25[ff] <> 0:
            WiWav25[ff],WiPer25[ff]=WindWave(Wi25[ff],Fd[ff],100)

#READ EXCEL INPUT################################################################################
try:
    # read Excel file inputs
    gp.AddMessage("\nReading Excel file inputs...")
    xlApp=Dispatch("Excel.Application")
    xlApp.Visible=0
    xlApp.DisplayAlerts=0
    xlApp.Workbooks.Open(InputTable)
    cell=xlApp.Worksheets("ProfileGeneratorInput")
    # sediment
    Diam=cell.Range("e8").Value # sediment diam (mm)
    A=cell.Range("e70").Value # sediment scale factor
    # tide         
    MSL=cell.Range("d14").Value # mean sea level
    HT=cell.Range("e14").Value # high tide elevation

    # read in habitat IDs
    if HabDirectory: 
        ExcelHabIDList=[]
        HabAbbrevList=[]
        temp=["e","f","g","h","i","j"]
        for i in range(len(temp)):
            if cell.Range(temp[i]+"18").Value not in [None,'']:
                ExcelHabIDList.append(int(cell.Range(temp[i]+"18").Value)) ## MUST BE AN INTEGER
                HabAbbrevList.append(cell.Range(temp[i]+"19").Value)

        Hab1Zip=zip(ExcelHabIDList,HabAbbrevList)
        Hab1Zip.sort()
        ExcelHabIDList,HabAbbrevList=zip(*Hab1Zip)

    # check if user needs backshore help
    BackHelp=cell.Range("e66").Value # 1) beach,2) mangroves/marshes,3) modifies,4) no change
    if BackHelp==1: # read ProfileGenerator information
        # foreshore    
        Slope=cell.Range("h34").Value # foreshore slope=1/Slope
        m=1.0/Slope # bed slope
    
        # read 'HelpCreatingBackshoreProfile' sheet
        BermCrest=cell.Range("d40").Value
        BermLength=cell.Range("e40").Value
    
        # estimate dune size from Short and Hesp
        DuneCheck=cell.Range("e67").Value # 1) yes,2) no,3) don't know
        if DuneCheck==1: # user has data
            DuneCrest=cell.Range("g45").Value
    
        elif DuneCheck==2: # no dunes
            DuneCrest=0;BermLength=50 # beach has no dune and infinitely long berm
                
        elif DuneCheck==3: 
            # wave climate data
            Hm=max(Hm,cell.Range("h45").Value) # modal wave height
            Tm=max(Tm,cell.Range("i45").Value) # modal wave period
            
            if Tm > 0:
                Hb=0.39*9.81**(1.0/5)*(Tm*Hm**2)**(2.0/5)
                a=0.00000126
                b=num.sqrt(3.61**2+1.18*(1.56*9.81*(Diam/1000.0)**3/a**2)**(1.0/1.53))-3.61
                ws=(a*b**1.53)/(0.0001*Diam) # fall velocity
                RTR=HT/Hb
                    
                if RTR > 3: # in this case,beach is not wave dominated,can't know value,so take zero
                    DuneCrest=0;BermLength=50
                else: # else,beach is wave dominated,we read Short and Hesp
                    Type=Hb/(ws*Tm)
                    if Type < 3:  DuneCrest=5
                    elif Type < 4:    DuneCrest=10
                    elif Type < 5:    DuneCrest=12
                    elif Type < 6:    DuneCrest=20
                    else:   DuneCrest=23 
            else:
                Tm=-1
                DuneCrest=2;BermLength=50 # beach has no dune and infinitely long berm
                    
    elif BackHelp==2:  # read marsh/mangrove parameters
        SlopeM=num.array([0,0,0,0])
        OffX=num.array([0,0,0,0])
        ShoreX=num.array([0,0,0,0])
        SlopeM[0]=cell.Range("e50").Value
        SlopeM[1]=cell.Range("e51").Value
        SlopeM[2]=cell.Range("e52").Value
        OffX[0]=cell.Range("f50").Value
        OffX[1]=cell.Range("f51").Value
        OffX[2]=cell.Range("f52").Value
        ShoreX[0]=cell.Range("g50").Value
        ShoreX[1]=cell.Range("g51").Value
        ShoreX[2]=cell.Range("g52").Value
    
    elif BackHelp==3: # read profile modification parameters
        SlopeMod=num.array([0,0,0,0])
        OffMod=num.array([0,0,0,0])
        ShoreMod=num.array([0,0,0,0])
        SlopeMod[0]=cell.Range("e57").Value
        SlopeMod[1]=cell.Range("e58").Value
        SlopeMod[2]=cell.Range("e59").Value
        SlopeMod[3]=cell.Range("e60").Value
        OffMod[0]=cell.Range("g57").Value
        OffMod[1]=cell.Range("g58").Value
        OffMod[2]=cell.Range("g59").Value
        OffMod[3]=cell.Range("g60").Value
        ShoreMod[0]=cell.Range("f57").Value
        ShoreMod[1]=cell.Range("f58").Value
        ShoreMod[2]=cell.Range("f59").Value
        ShoreMod[3]=cell.Range("f60").Value
    
    # save changes and close Excel file
    xlApp.ActiveWorkbook.Close(SaveChanges=0) # don't save changes
    xlApp.Quit()
    
except:
    gp.AddError("\nError reading Excel file inputs")
    xlApp.ActiveWorkbook.Close(SaveChanges=0)
    xlApp.Quit()
    raise Exception

# cut,read,or create nearshore bathy profile
if ProfileQuestion=="(1) Yes": # model extracts value from GIS layers
    gp.AddMessage("\nCreating profile points from transect...")
    # create transect and read transect file
    gp.Buffer_analysis(LandPoint,LandPoint_Buff,str(BufferDist)+" Meters","FULL","ROUND","NONE","")
    gp.Extent=LandPoint_Buff
    gp.PolygonToLine_management(LandPoly,Shoreline)
    gp.Extent=""
    gp.Clip_analysis(Shoreline,LandPoint_Buff,Shoreline_Buff_Clip,"")
    # check to make sure that clipped shoreline is not empty FC
    if gp.GetCount_management(Shoreline_Buff_Clip)==0:
        gp.AddError("Shoreline was not found within "+str(BufferDist)+" meters of 'LandPoint' input.  \
                     Either increase the buffer distance or move the 'LandPoint' input closer to the coastline.")
        raise Exception
    gp.Dissolve_management(Shoreline_Buff_Clip,Shoreline_Buff_Clip_Diss,"","","MULTI_PART","UNSPLIT_LINES")

    # set coordinate system to same projection (in meters) as the shoreline point input
    gp.outputCoordinateSystem=LandPoint
    cur=gp.UpdateCursor(LandPoint)
    row=cur.Next()
    feat=row.Shape
    midpoint=feat.Centroid
    midList=shlex.split(midpoint)
    midList=[float(s) for s in midList]
    midx=midList[0]
    midy=midList[1]
    del cur,row

    # grab coordinates of the start and end of the coastline segment
    cur=gp.SearchCursor(Shoreline_Buff_Clip_Diss)
    row=cur.Next()
    counter=1
    feat=row.Shape
    firstpoint=feat.FirstPoint
    lastpoint=feat.LastPoint
    startList=shlex.split(firstpoint)
    endList=shlex.split(lastpoint)
    startx=float(startList[0])
    starty=float(startList[1])
    endx=float(endList[0])
    endy=float(endList[1])

    # diagnose the type of perpendicular transect to create (PerpTransType)
    PerpTransType=0
    if starty==endy or startx==endx:
        if starty==endy:
            y1=midy+TransectDist
            y2=midy-TransectDist
            x1=midx
            x2=midx
            PerpTransType=1
        if startx==endx:
            y1=midy
            y2=midy 
            x1=midx+TransectDist
            x2=midx-TransectDist
            PerpTransType=2
    else:
        # get the slope of the line
        m=((starty-endy)/(startx-endx))
        # get the negative reciprocal
        NegRecip=-1*((startx-endx)/(starty-endy))

        if m > 0:
            # increase x-values,find y
            if m >= 1:
                y1=NegRecip*(TransectDist)+midy
                y2=NegRecip*(-TransectDist)+midy
                x1=midx+TransectDist
                x2=midx-TransectDist
                PerpTransType=3
            # increase y-values,find x
            if m < 1:
                y1=midy+TransectDist
                y2=midy-TransectDist
                x1=(TransectDist/NegRecip)+midx
                x2=(-TransectDist/NegRecip)+midx
                PerpTransType=4
        if m < 0:
            # add to x,find y-values
            if m >= -1:
            # add to y,find x-values
                y1=midy+TransectDist
                y2=midy-TransectDist
                x1=(TransectDist/NegRecip)+midx
                x2=(-TransectDist/NegRecip)+midx
                PerpTransType=5
            if m < -1:
                y1=NegRecip*(TransectDist)+midy
                y2=NegRecip*(-TransectDist)+midy
                x1=midx+TransectDist
                x2=midx-TransectDist
                PerpTransType=6
    del cur
    del row

    # grab projection spatial reference from 'LandPoint'
    dataDesc=gp.describe(LandPoint)
    spatialRef=dataDesc.SpatialReference
    gp.CreateFeatureClass_management(interws,"PT1.shp","POINT","#","#","#",spatialRef)
    gp.CreateFeatureClass_management(interws,"PT2.shp","POINT","#","#","#",spatialRef)

    # create two point transects, each point is 1 meter away from the previous    
    cur1=gp.InsertCursor(PT1)
    cur2=gp.InsertCursor(PT2)
    while TransectDist <= RadLineDist/2.0:
        # call 'PTCreate' function to use the correct perpendicular transect formula based on coastline slope (m)
        x1,y1,x2,y2=PTCreate(PerpTransType,midx,midy,TransectDist)
        row1=cur1.NewRow()
        pnt=gp.CreateObject("POINT")
        pnt.x=x1
        pnt.y=y1
        row1.shape=pnt
        cur1.InsertRow(row1)
        row2=cur2.NewRow()
        pnt=gp.CreateObject("POINT")
        pnt.x=x2
        pnt.y=y2
        row2.shape=pnt
        cur2.InsertRow(row2)
        TransectDist=TransectDist+1
    del cur1,row1
    del cur2,row2

    # extract depth values from 'BathyGrid' to point transects
    gp.ExtractValuesToPoints_sa(PT1,BathyGrid,PT1_Z,"INTERPOLATE")
    gp.ExtractValuesToPoints_sa(PT2,BathyGrid,PT2_Z,"INTERPOLATE")
    PT1_Z=AddField(PT1_Z,"PT_ID","LONG","","")        
    gp.CalculateField_management(PT1_Z,"PT_ID","[FID]+1","VB")
    PT2_Z=AddField(PT2_Z,"PT_ID","LONG","","")        
    gp.CalculateField_management(PT2_Z,"PT_ID","[FID]+1","VB")    

    # create depth lists of two point transects
    Dmeas1=[]
    cur=gp.UpdateCursor(PT1_Z)
    row=cur.Next()
    while row:
        Dmeas1.append(row.GetValue("RASTERVALU"))
        cur.UpdateRow(row)
        row=cur.next()
    del cur,row
    Dmeas2=[]
    cur=gp.UpdateCursor(PT2_Z)
    row=cur.Next()
    while row:  
        Dmeas2.append(row.GetValue("RASTERVALU"))
        cur.UpdateRow(row)
        row=cur.next()
    del cur,row

    # find which point transect hits water first
    DepthStart1=1
    for DepthValue1 in Dmeas1:
        if DepthValue1 < 0.0 and DepthValue1 <> -9999.0:
            break
        DepthStart1=DepthStart1+1
    DepthStart2=1
    for DepthValue2 in Dmeas2:
        if DepthValue2 < 0.0 and DepthValue2 <> -9999.0:
            break
        DepthStart2=DepthStart2+1
        
    # create final lists of cross-shore distance (Dx) and depth (Dmeas)
    Dx=[]   
    Dmeas=[]
    counter=0
    if DepthStart1 < DepthStart2:
        for i in range(DepthStart1-1,len(Dmeas1)):
            if Dmeas1[i] < 0.0 and Dmeas1[i] <> -9999.0:
                Dx.append(counter)
                Dmeas.append(Dmeas1[i])
                counter=counter+1
            else:
                break
    else:
        for j in range(DepthStart2-1,len(Dmeas2)):
            if Dmeas2[j] < 0.0 and Dmeas2[j] <> -9999.0:
                Dx.append(counter)
                Dmeas.append(Dmeas2[j])
                counter=counter+1
            else:
                break

    if len(Dmeas1)==0 and len(Dmeas2)==0:
        gp.AddError("\nNeither transect overlaps the seas.  Please check the location of your 'LandPoint' and bathymetry inputs.")
        raise Exception
    else: # save cut profile
        Dorig=Dmeas1[:]
        Dorig.extend(Dmeas2)
        Xorig=[ii for ii in range(len(Dorig))]

        file=open(ProfileCutGIS,"w")
        for i in range(0,len(Dorig)):
            file.writelines(str(Xorig[i])+"\t"+str(Dorig[i])+"\n")
        file.close()

    # create txt for bathy portion
    file=open(BathyProfile,"w")
    for i in range(0,len(Dmeas)):
        file.writelines(str(Dx[i])+"\t"+str(Dmeas[i])+"\n")
    file.close()

    # create final point transect file
    if DepthStart1 < DepthStart2:
        gp.Select_analysis(PT1_Z,Profile_Pts,"\"PT_ID\" > "+str(DepthStart1-1)+" AND \"PT_ID\" < "+str(DepthStart1+counter))
        if HabDirectory:
            # add near and backshore to profile for habitat extraction
            gp.Select_analysis(PT1_Z,PT_Z_Near,"\"PT_ID\" <= "+str(DepthStart1-1))
            PT_Z_Near=AddField(PT_Z_Near,"DEPTH","DOUBLE","","")
            gp.CalculateField_management(PT_Z_Near,"DEPTH","[RASTERVALU]","VB")
            gp.DeleteField_management(PT_Z_Near,"RASTERVALU")
            PT2_Z=AddField(PT2_Z,"DEPTH","DOUBLE","","")
            gp.CalculateField_management(PT2_Z,"DEPTH","[RASTERVALU]","VB")
            gp.DeleteField_management(PT2_Z,"RASTERVALU")
            gp.CalculateField_management(PT2_Z,"PT_ID","[PT_ID]*-1","VB")
            gp.Select_analysis(PT2_Z,Backshore_Pts,"\"PT_ID\" < 0 AND \"PT_ID\" > -2001")
            
    else:
        gp.Select_analysis(PT2_Z,Profile_Pts,"\"PT_ID\" > "+str(DepthStart2-1)+" AND \"PT_ID\" < "+str(DepthStart2+counter))
        if HabDirectory:
            # add near and backshore to profile for habitat extraction
            gp.Select_analysis(PT2_Z,PT_Z_Near,"\"PT_ID\" <= "+str(DepthStart2-1))
            PT_Z_Near=AddField(PT_Z_Near,"DEPTH","DOUBLE","","")
            gp.CalculateField_management(PT_Z_Near,"DEPTH","[RASTERVALU]","VB")
            gp.DeleteField_management(PT_Z_Near,"RASTERVALU")
            PT1_Z=AddField(PT1_Z,"DEPTH","DOUBLE","","")
            gp.CalculateField_management(PT1_Z,"DEPTH","[RASTERVALU]","VB")
            gp.DeleteField_management(PT1_Z,"RASTERVALU")
            gp.CalculateField_management(PT1_Z,"PT_ID","[PT_ID]*-1","VB")
            gp.Select_analysis(PT1_Z,Backshore_Pts,"\"PT_ID\" < 0 AND \"PT_ID\" > -2001")

    # add and calculate field for "DEPTH"
    Profile_Pts=AddField(Profile_Pts,"DEPTH","DOUBLE","","")
    gp.CalculateField_management(Profile_Pts,"DEPTH","[RASTERVALU]","VB")
    gp.DeleteField_management(Profile_Pts,"RASTERVALU")

    # merge 'Profile_Pts' with 'Land Point' and backshore profile up to 2km
    if HabDirectory:
        MergeExpr=Profile_Pts+";"+PT_Z_Near+";"+LandPoint+";"+Backshore_Pts
        gp.Merge_management(MergeExpr,Profile_Pts_Merge,"")

    # smooth profile and create x axis
    lx=len(Dmeas) # length of original data
    Dx=num.array(Dx)
    Dmeas=num.array(Dmeas)# shoreline starts at x=0
    
    yd=[Dmeas[ii] for ii in range(len(Dx))]
    xd=[Dx[ii] for ii in range(len(Dx))]
    SmoothValue=(SmoothParameter/100.0)*len(Dmeas)
    TempY=SignalSmooth.smooth(Dmeas,round(SmoothValue,2),'flat') # smooth function
    TempX=num.array(Dx)

    # remove portions offshore that are shallower than average depth abv deepest point
    LocDeep=Indexed(TempY,min(TempY)) #Locate deepest point
    davg=mean(TempY);davg=average([davg,min(TempY)])
    out=num.nonzero(TempY<davg);out=out[0] #Locate points deeper than avg depth

    loc=out[-1]
    if loc>LocDeep: # if point is offshore of deepest point
        out=num.arange(loc,len(yd),1)
        yd=num.delete(yd,out,None)
        xd=num.delete(Dx,out,None);xd=xd-xd[0]
        TempY[out]=0
        TempX[out]=-1         
    lx=len(xd) 
    
    # insert 'TempY' and 'TempX' in shapefile output
    Profile_Pts=AddField(Profile_Pts,"SM_BATHY_X","DOUBLE","","")
    Profile_Pts=AddField(Profile_Pts,"SM_BATHY_Y","DOUBLE","","")
    cur=gp.UpdateCursor(Profile_Pts)
    row=cur.Next()
    j=0
    while row:
        row.SetValue("SM_BATHY_X",TempX[j])
        row.SetValue("SM_BATHY_Y",TempY[j])
        j+=1
        cur.UpdateRow(row)
        row=cur.Next()
    del cur,row,TempX,TempY

    # read habitat GIS layers to profile
    if HabDirectory:
        gp.AddMessage("...locating each habitat's presence along the profile")
        gp.workspace=HabDirectory
        fcList=gp.ListFeatureClasses("*","all")
        fc=fcList.Next()
        HabLyrList=[]
        HabIDList=[]
        while fc:
            checkGeometry(fc,"Polygon","Natural Habitat")
            checkInteger(fc)
            ckProjection(fc)
            HabLyrList.append(fc)
            fc2=fc[::-1]
            j=fc2.find('_')
            indexS=len(fc)-j-1
            indexE=fc.find(".")
            fc_ID=fc[indexS+1:indexE]
            HabIDList.append(int(fc_ID))
            fc=fcList.Next()
        del fc

        Hab2Zip=zip(HabIDList,HabLyrList)
        Hab2Zip.sort()
        HabIDList,HabLyrList=zip(*Hab2Zip)

        # check that 'HabDirectory' and Excel input are consistent
        if ExcelHabIDList <> HabIDList:
            gp.AddError("There is an inconsistency between the number of habitat layers in the specified directory and the input spreadsheet.")
            raise Exception

        gp.workspace=gp.GetParameterAsText(0) # reset workspace
        gp.Extent=Profile_Pts_Merge # revise extent
        
        # rasterize the layers and generate zone of influence
        IntersectExpr=''
        AbbrevList=['MG','MR','SG','DN','CR','OT']
        ExcludeList=["FID","Shape","Id","PT_ID","DEPTH"]
        for i in range(0,len(HabLyrList)):
            HabVector=HabDirectory+"\\"+HabLyrList[i]
            HabVector=AddField(HabVector,"ID","SHORT","0","0")
            gp.CalculateField_management(HabVector,"ID",1,"VB")
            gp.FeatureToRaster_conversion(HabVector,"ID",interws+HabAbbrevList[i],"10")
            gp.BuildRasterAttributeTable_management(interws+HabAbbrevList[i], "Overwrite")                   
            if gp.GetCount(interws+HabAbbrevList[i]) > 0:
                pass
                gp.Reclassify_sa(interws+HabAbbrevList[i],"VALUE","1 1;NODATA 0",interws+HabAbbrevList[i]+"_rc","DATA")
                gp.ExtractValuesToPoints_sa(Profile_Pts_Merge,interws+HabAbbrevList[i]+"_rc",interws+HabAbbrevList[i]+".shp","NONE")
                gp.AddField_management(interws+HabAbbrevList[i]+".shp",HabAbbrevList[i],"SHORT","0","0","","","NON_NULLABLE","NON_REQUIRED","")
                gp.CalculateField_management(interws+HabAbbrevList[i]+".shp",HabAbbrevList[i],"[RASTERVALU]","VB")
                gp.DeleteField_management(interws+HabAbbrevList[i]+".shp","RASTERVALU")
                if i==0:
                    IntersectExpr=IntersectExpr+interws+HabAbbrevList[i]+".shp "+str(i+1)
                else:
                    IntersectExpr=IntersectExpr+"; "+interws+HabAbbrevList[i]+".shp "+str(i+1)
        # intersect the various habitat profile point plots
        gp.Intersect_analysis(IntersectExpr,Profile_Pts_Hab,"NO_FID","","INPUT")

        # delete extra fields
        DeleteFieldList=[]
        HabFieldList=[]
        fieldList=gp.ListFields(Profile_Pts_Hab,"*","All")
        field=fieldList.Next()
        while field <> None:
            if field.Name not in AbbrevList+ExcludeList:
                DeleteFieldList.append(field.Name)
            if field.Name in AbbrevList:
                HabFieldList.append(field.Name)
            field=fieldList.Next()
        del fieldList,field
        gp.DeleteField_management(Profile_Pts_Hab,DeleteFieldList)

        # add all habitat abbreviation fields, even if not part of inputs
        for k in range(0,len(AbbrevList)):
            if AbbrevList[k] not in HabFieldList:
                Profile_Pts_Hab=AddField(Profile_Pts_Hab,AbbrevList[k],"SHORT","0","0")

        # read 'Profile_Pts_Hab' to array 'ProfileHabArray'
        ProfileHabLength = gp.GetCount_management(Profile_Pts_Hab)
        ProfileHabList = np.zeros(ProfileHabLength*8, dtype=np.float64)
        ProfileHabArray = np.reshape(ProfileHabList, (ProfileHabLength,8)) # PT_ID, DEPTH, MG, MR, SG, DN, CR, OT
        cur=gp.UpdateCursor(Profile_Pts_Hab)
        row=cur.Next()
        j=0
        while row:  
            ProfileHabArray[j][0]=row.GetValue("PT_ID")
            ProfileHabArray[j][1]=row.GetValue("DEPTH")
            for i in range(0,len(AbbrevList)):
                ProfileHabArray[j][i+2]=row.GetValue(AbbrevList[i])
            cur.UpdateRow(row)
            row=cur.next()
            j+=1
        del cur,row

        ProfileHabArray = ProfileHabArray[ProfileHabArray[:,0].argsort()] # sort the array by 'PT_ID'

        # Export bathy and vegetation information       

        TextData=open(html_txt+"HabitatLocation.txt","w")
        for i in range(0,ProfileHabLength):
            for j in range(0,7):
                TextData.write(str(ProfileHabArray[i][j])+" ")
            TextData.write("\n")
        TextData.close() 
        
        temp=transpose(ProfileHabArray)
        TempX=temp[0]
        TempY=temp[1]
        MG=temp[2];MR=temp[3];SG=temp[4];DN=temp[5];CR=temp[6];OT=temp[7]
        MG[find(MG==-999)]=0;SG[find(SG==-999)]=0;MR[find(MR==-999)]=0
        DN[find(DN==-999)]=0;CR[find(CR==-999)]=0;OT[find(OT==-999)]=0
        
        temp=num.nonzero(MG);temp=temp[0]
        la=num.nonzero(diff(temp)<>1);la=la[0]       
        if len(la)>0:
            begMGx=num.arange(0,len(la)+1,1)*0;finMGx=num.array(begMGx)
            begMGy=num.array(begMGx);finMGy=num.array(begMGx)
            temp1=num.append(temp[0],temp[la],None);temp1=num.append(temp1,temp[la+1],None)
            temp1=num.append(temp1,temp[-1],None);temp1=sort(temp1)
            for kk in range(len(temp1)/2):
                begMGx[kk]=TempX[temp1[2*kk]];begMGy[kk]=TempY[temp1[2*kk]]
                finMGx[kk]=TempX[temp1[2*kk+1]];finMGy[kk]=TempY[temp1[2*kk+1]]
        elif len(temp)>0:
            begMGx=[TempX[temp[0]]];begMGy=[TempY[temp[0]]]
            finMGx=[TempX[temp[-1]]];finMGy=[TempY[temp[-1]]];
        else:
            begMGx=[];finMGx=[];begMGy=[];finMGy=[];
        begMGx=num.array(begMGx);finMGx=num.array(finMGx)

        temp=num.nonzero(SG);temp=temp[0]
        la=num.nonzero(diff(temp)<>1);la=la[0]       
        if len(la)>0:
            begSGx=num.arange(0,len(la)+1,1)*0;finSGx=num.array(begSGx)
            begSGy=num.array(begSGx);finSGy=num.array(begSGx)
            temp1=num.append(temp[0],temp[la],None);temp1=num.append(temp1,temp[la+1],None)
            temp1=num.append(temp1,temp[-1],None);temp1=sort(temp1)
            for kk in range(len(temp1)/2):
                begSGx[kk]=TempX[temp1[2*kk]];begSGy[kk]=TempY[temp1[2*kk]]
                finSGx[kk]=TempX[temp1[2*kk+1]];finSGy[kk]=TempY[temp1[2*kk+1]]
        elif len(temp)>0:
            begSGx=[TempX[temp[0]]];begSGy=[TempY[temp[0]]]
            finSGx=[TempX[temp[-1]]];finSGy=[TempY[temp[-1]]]
        else:
            begSGx=[];finSGx=[];begSGy=[];finSGy=[];
        begSGx=num.array(begSGx);finSGx=num.array(finSGx)

        temp=num.nonzero(MR);temp=temp[0]
        la=num.nonzero(diff(temp)<>1);la=la[0]       
        if len(la)>0:
            begMRx=num.arange(0,len(la)+1,1)*0;finMRx=num.array(begMRx)
            begMRy=num.array(begMRx);finMRy=num.array(begMRx)
            temp1=num.append(temp[0],temp[la],None);temp1=num.append(temp1,temp[la+1],None)
            temp1=num.append(temp1,temp[-1],None);temp1=sort(temp1)
            for kk in range(len(temp1)/2):
                begMRx[kk]=TempX[temp1[2*kk]];begMRy[kk]=TempY[temp1[2*kk]]
                finMRx[kk]=TempX[temp1[2*kk+1]];finMRy[kk]=TempY[temp1[2*kk+1]]
        elif len(temp)>0:
            begMRx=[TempX[temp[0]]];begMRy=[TempY[temp[0]]]
            finMRx=[TempX[temp[-1]]];finMRy=[TempY[temp[-1]]]
        else:
            begMRx=[];finMRx=[];begMRy=[];finMRy=[];
        begMRx=num.array(begMRx);finMRx=num.array(finMRx)

        temp=num.nonzero(CR);temp=temp[0]
        la=num.nonzero(diff(temp)<>1);la=la[0]       
        if len(la)>0:
            begCRx=num.arange(0,len(la)+1,1)*0;finCRx=num.array(begCRx)
            begCRy=num.array(begCRx);finCRy=num.array(begCRx)
            temp1=num.append(temp[0],temp[la],None);temp1=num.append(temp1,temp[la+1],None)
            temp1=num.append(temp1,temp[-1],None);temp1=sort(temp1)
            for kk in range(len(temp1)/2):
                begCRx[kk]=TempX[temp1[2*kk]];begCRy[kk]=TempY[temp1[2*kk]]
                finCRx[kk]=TempX[temp1[2*kk+1]];finCRy[kk]=TempY[temp1[2*kk+1]]
        elif len(temp)>0:
            begCRx=[TempX[temp[0]]];begCRy=[TempY[temp[0]]]
            finCRx=[TempX[temp[-1]]];finCRy=[TempY[temp[-1]]]
        else:
            begCRx=[];finCRx=[];begCRy=[];finCRy=[];
        begCRx=num.array(begCRx);finCRx=num.array(finCRx)

        temp=num.nonzero(DN);temp=temp[0]
        la=num.nonzero(diff(temp)<>1);la=la[0]       
        if len(la)>0:
            begDNx=num.arange(0,len(la)+1,1)*0;finDNx=num.array(begDNx)
            begDNy=num.array(begDNx);finDNy=num.array(begDNx)
            temp1=num.append(temp[0],temp[la],None);temp1=num.append(temp1,temp[la+1],None)
            temp1=num.append(temp1,temp[-1],None);temp1=sort(temp1)
            for kk in range(len(temp1)/2):
                begDNx[kk]=TempX[temp1[2*kk]];begDNy[kk]=TempY[temp1[2*kk]]
                finDNx[kk]=TempX[temp1[2*kk+1]];finDNy[kk]=TempY[temp1[2*kk+1]]
        elif len(temp)>0:
            begDNx=[TempX[temp[0]]];begDNy=[TempY[temp[0]]]
            finDNx=[TempX[temp[-1]]];finDNy=[TempY[temp[-1]]]
        else:
            begDNx=[];finDNx=[];begDNy=[];finDNy=[]
        begDNx=num.array(begDNx);finDNx=num.array(finDNx)
        
        temp=num.nonzero(OT);temp=temp[0]
        la=num.nonzero(diff(temp)<>1);la=la[0]       
        if len(la)>0:
            begOTx=num.arange(0,len(la)+1,1)*0;finOTx=num.array(begOTx)
            begOTy=num.array(begOTx);finOTy=num.array(begOTx)
            temp1=num.append(temp[0],temp[la],None);temp1=num.append(temp1,temp[la+1],None);
            temp1=num.append(temp1,temp[-1],None);temp1=sort(temp1)
            for kk in range(len(temp1)/2):
                begOTx[kk]=TempX[temp1[2*kk]];begOTy[kk]=TempY[temp1[2*kk]]
                finOTx[kk]=TempX[temp1[2*kk+1]];finOTy[kk]=TempY[temp1[2*kk+1]]
        elif len(temp)>0:
            begOTx=[TempX[temp[0]]];begOTy=[TempY[temp[0]]]
            finOTx=[TempX[temp[-1]]];finOTy=[TempY[temp[-1]]];
        else:
            begOTx=[];finOTx=[];begOTy=[];finOTy=[];
        begOTx=num.array(begOTx);finOTx=num.array(finOTx)
        
# upload user's profile
elif ProfileQuestion=="(2) No,but I will upload a cross-shore profile":
    gp.AddMessage("\nRetrieving your profile...")
    # read in user's cross-shore profile
    TextData=open(CSProfile,"r") 
    Dx=[];Dmeas=[]
    for line in TextData.read().strip("\n").split("\n"):
        linelist=[float(s) for s in line.split("\t")] # split the list by tab delimiter
        Dx.append(linelist[0])
        Dmeas.append(linelist[1])
    TextData.close()
      
    Dmeas=num.array(Dmeas);Dx=num.array(Dx);Lx=len(Dx)
    if len(Dx) > 5:
        F=interp1d(Dx,Dmeas);xd=num.arange(Dx[0],Dx[-1],1)
        temp=F(xd);xd=xd-xd[0];lx=len(xd)

        yd=num.array(temp)
    else:
        xd=[Dx[xx] for xx in range(Lx)]
        yd=[Dmeas[xx] for xx in range(Lx)];lx=len(yd)

    if BackHelp==1:
        keep=num.nonzero(yd<=0);keep=keep[0]
        xd=xd[keep];yd=yd[keep]
        if len(keep)<len(yd):
            gp.AddMessage("\nA portion of your uploaded profile above 'Mean Lower Low Water' was removed so we can build your backshore profile.")

    # grab projection spatial reference and x,y from 'LandPoint'
    gp.outputCoordinateSystem=LandPoint
    cur=gp.UpdateCursor(LandPoint)
    row=cur.Next()
    feat=row.Shape
    midpoint=feat.Centroid
    midList=shlex.split(midpoint)
    midList=[float(s) for s in midList]
    midx=midList[0]
    midy=midList[1]
    del cur,row

    dataDesc=gp.describe(LandPoint)
    spatialRef=dataDesc.SpatialReference
    # add values from uploaded profile to shapefile of multiple points overlapping 'LandPoint'
    gp.CreateFeatureClass_management(maps,"UploadedProfile.shp","POINT","#","#","#",spatialRef)
    cur=gp.InsertCursor(UploadedProfile)
    PtID=0
    while PtID < len(Dx):
        row=cur.NewRow()
        pnt=gp.CreateObject("POINT")
        pnt.x=float(midx)
        pnt.y=float(midy)
        row.shape=pnt
        cur.InsertRow(row)
        PtID+=1
    del cur,row

    UploadedProfile=AddField(UploadedProfile,"XSHOREDIST","LONG","8","")
    UploadedProfile=AddField(UploadedProfile,"DEPTH","DOUBLE","","")
    cur=gp.UpdateCursor(UploadedProfile)
    row=cur.Next()
    i=0
    while row:
        row.SetValue("XSHOREDIST",Dx[i])
        row.SetValue("DEPTH",Dmeas[i])
        cur.UpdateRow(row)
        row=cur.Next()
        i+=1
    del cur,row
      
# equilibrium beach profile,in case we don't have nearshore bathy
elif ProfileQuestion=="(3) No,please create a theoretical profile for me":
    if Diam < 0.1:
        gp.AddError("\nCannot create an equilibrium profile for cohesive/fine sediments (size smaller than 0.1mm)")
        raise Exception
    else:
        gp.AddMessage("\nCreating theoretical profile for you...")

    x=num.arange(0.0,10001.0,1.0) # long axis
    temp=2.0/3
    Dmeas=-A*x**(temp)# eq. profile
    out=num.nonzero(Dmeas<-20);temp1=out[0]
    out=num.nonzero(Dmeas>-1);temp2=out[0]
    out=num.append(temp1,temp2)
    Dmeas=num.delete(Dmeas,out,None) # water depths down to -20
    Dx=num.delete(x,out,None);lx=len(Dx)

    yd=num.array(Dmeas);xd=num.array(Dx)

xd2=[xd[ii] for ii in range(len(xd))]
SmoothValue=round((SmoothParameter/100.0)*len(xd),2)
yd2=SignalSmooth.smooth(yd,SmoothValue,'flat')


# profile modification
gp.AddMessage("...customizing depth profile")
if BackHelp==1: # create backshore profile for beach systems 
    # smooth the signal
    SmoothValue=round((SmoothParameter/100.0)*len(xd),2)
    yd=SignalSmooth.smooth(yd,SmoothValue,'flat');yd=yd[::-1]      
    
    x=num.arange(0.0,10001.0,1.0) # long axis
    BermCrest=BermCrest+MSL; #yd is referenced to MLLW; Need to reference all to MSL
    # add foreshore
    yf=1.0/Slope*x+yd[-1]
    Above=num.nonzero(yf > BermCrest)
    xf=num.delete(x,Above[0],None)
    yf=num.delete(yf,Above[0],None) # remove values that are above BermCrest

    # berm and dune
    if DuneCheck==2: # no dunes are present,just berm   # 1=Yes,2=No,3=Dont know
        xb=num.arange(0,100,1)
        yb=num.array(len(xb)*[0.0])+BermCrest # horizontal berm 100m long
    elif DuneCheck==3 and RTR > 3: # user doesn't know,and not wave Dominated: no dunes,just berm
        xb=num.arange(0,100,1)
        yb=num.array(len(xb)*[0.0])+BermCrest # horizontal berm 100m long
    else: # dune exists...we'll create it as sinusoid for representation
        xb=num.arange(0,1000.1,1)
        yb=num.array(len(xb)*[0.0])+BermCrest # berm profile
        if BermLength <> 0: # berm width in front of dune
            Toe=abs(xb-BermLength).argmin()# locate toe to separate berm and dune
        else: Toe=0
        
        # dune profile
        DuneWidth=3.0*DuneCrest # width of sinusoid....won't use...for plotting purposes only
        yb[Toe:-1]=float(DuneCrest)*num.sin(2.0*pi*(xb[Toe:-1]-xb[Toe])/float(DuneWidth))+(BermCrest)
        DunePlotEnd=xb[Toe]+3.0*DuneWidth
        DunePlotSmall=xb[Toe]+DuneCrest

        out=num.arange(DunePlotEnd,len(yb),1)
        yb[DunePlotSmall:-1]=yb[DunePlotSmall:-1]/10.0
        yb[DunePlotSmall:-1]=yb[DunePlotSmall:-1]+yb[DunePlotSmall-1]-yb[DunePlotSmall]

        xb=num.delete(xb,out,None)
        yb=num.delete(yb,out,None)
        yb[-1]=yb[-2]
        if DuneCrest>0:
            temp1=num.array(yb)
            temp2=temp1[0]
            temp1=temp1-temp2;temp1=temp1/max(temp1)*(DuneCrest)
            yb=temp1+temp2;
  
    # combine all vectors together
    xf=xf+xd[-1];xb=xb+xf[-1] # make one long x-axis
    xd=xd.tolist();yd=yd.tolist() # transform into lists
    xf=xf.tolist();yf=yf.tolist()
    xb=xb.tolist();yb=yb.tolist()
  
    yd.extend(yf);xd.extend(xf) # make one y-axis
    xd.extend(xb);yd.extend(yb)
    yd=num.array(yd);xd=num.array(xd)
    
elif BackHelp==2: # modify profile for mangroves/marshes
    Xmod=[xd[i] for i in range(lx)];Xmod=num.array(Xmod)
    Ymod=[yd[i] for i in range(lx)];Ymod=num.array(Ymod)
    out=num.nonzero(SlopeM < 0);out=out[0]
    SlopeM=num.delete(SlopeM,out,None)
    
    # modify existing profile
    for oo in range(len(SlopeM)):
        SlopeMod1=SlopeM[oo]
        OffMod1=Xmod[-1]-OffX[oo];ShoreMod1=Xmod[-1]-ShoreX[oo] 

        if ShoreMod1-OffMod1<>0:
            Xmod,Ymod=SlopeModif(Xmod,Ymod,SlopeMod1,OffMod1,ShoreMod1)
    
    # resample on vector with dx=1
    F=interp1d(Xmod,Ymod);Xmod=num.arange(Xmod[0],Xmod[0]+len(Xmod),1)
    Ymod=F(Xmod)

    # smooth the signal
    SmoothValue=round((SmoothParameter/100.0)*len(xd),2)
    yd=SignalSmooth.smooth(Ymod,SmoothValue,'flat');yd=yd[::-1];
    loc=Indexed(yd,0.0);xd=Xmod-Xmod[loc]
    
elif BackHelp==3: # modify profile with straight lines 
    yd=yd[::-1]
    SlopeMod=num.array([600,0,-1,0])
    
    Xmod=[xd[i] for i in range(lx)];Xmod=num.array(Xmod)
    Ymod=[yd[i] for i in range(lx)];Ymod=num.array(Ymod)
    loc=num.nonzero(SlopeMod < 0);loc=loc[0]
    SlopeMod=num.delete(SlopeMod,loc,None)

    # remove portions of existing profile
    out=[]
    for oo in range(len(loc)):
        OffDel=Xmod[-1]-OffMod[loc[oo]]
        ShoreDel=Xmod[-1]-ShoreMod[loc[oo]]

        of1=Indexed(Xmod,OffDel);sho1=Indexed(Xmod,ShoreDel) # locate offshore and shoreward points
        temp=num.arange(of1,sho1+1,1);out=num.append(out,temp,None)
    out=[int(out[ii]) for ii in range(len(out))]

    Ymod=num.delete(Ymod,out,None) # remove points from Ymod
    Xmod=num.delete(Xmod,out,None) # remove points from Xmod
    if len(Ymod) < 4:
        gp.AddError("Too many points removed,the profile no longer exists")
        raise Exception

     # modify existing profile
    for oo in range(len(SlopeMod)):
        SlopeMod1=SlopeMod[oo]
        OffMod1=Xmod[-1]-OffMod[oo];ShoreMod1=Xmod[-1]-ShoreMod[oo]

        if ShoreMod1 < OffMod1:
            gp.AddError("In Modification 1,XInshore should be larger than XOffshore.")
            raise Exception
        if ShoreMod1-OffMod1<>0:
            Xmod,Ymod=SlopeModif(Xmod,Ymod,SlopeMod1,OffMod1,ShoreMod1)
    
    # resample on vector with dx=1
    F=interp1d(Xmod,Ymod);Xmod=num.arange(Xmod[0],Xmod[0]+len(Xmod),1)
    Ymod=F(Xmod)

    # smooth the signal
    SmoothValue=round((SmoothParameter/100.0)*len(xd),2)
    yd=SignalSmooth.smooth(Ymod,SmoothValue,'flat');yd=yd[::-1];
    loc=Indexed(yd,0.0);xd=Xmod-Xmod[loc]

else:
    # smooth the signal
    SmoothValue=round((SmoothParameter/100.0)*len(xd),2)
    yd=SignalSmooth.smooth(yd,SmoothValue,'flat');

# plot
gp.AddMessage("...plotting profile and creating outputs\n")
# depth limits for plotting
DeepLoc=argmin(abs(yd-(-3)));

Fig3=1;Fig2=1;Fig6=0
# plot and save
if BackHelp==1:
    if ProfileQuestion=="(1) Yes":
        Dorig=num.array(Dorig);Xorig=num.array(Xorig)
        figure(2)
        plot(xd,yd,xd,yd*0,'k',xd,yd*0-MSL,'--k',xd,yd*0+HT-MSL,'-.k',linewidth=2);grid()
        legend(('Elevation','Mean Sea Level','Mean Low Water','Mean High Water'),'upper right')
        ylabel('Depth [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        title('Created Profile',size='large',weight='bold')
        savefig(html_txt+"ProfilePlot1.png",dpi=(640/8));Fig2=1
        
        figure(3)
        plot(Xorig,Dorig,Xorig,Dorig*0,'k',linewidth=2);grid()
        title('Elevation seaward and landward of chosen location',size='large',weight='bold')
        ylabel('Elevation [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        savefig(html_txt+"ProfilePlot3.png",dpi=(640/8))
                
    elif ProfileQuestion=="(2) No,but I will upload a cross-shore profile":
        figure(2)
        keep=num.nonzero(yd <= 0);keep=keep[0]
        temp1=xd[keep];temp2=yd[keep]
        plot(Dx,Dmeas,temp1,temp2,Dx,Dmeas*0,'k',linewidth=2);grid()
        legend(('Initial Profile','Smoothed Profile'),'upper right')
        ylabel('Depth [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        title('Bathymetry Profile-Smoothing Factor='+str(SmoothParameter),size='large',weight='bold')
        savefig(html_txt+"ProfilePlot3.png",dpi=(640/8))

        figure(3)
        plot(xd,yd,xd,yd*0,'k',linewidth=2);grid()
        ylabel('Depth [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        title('Created Profile',size='large',weight='bold')
        savefig(html_txt+"ProfilePlot1.png",dpi=(640/8))

    elif ProfileQuestion=="(3) No,please create a theoretical profile for me":
        figure(2)
        plot(xd,yd,xd,yd*0,'k',linewidth=2);grid()
        ylabel('Depth [m]',weight='bold')
        title('Created Profile',size='large',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        savefig(html_txt+"ProfilePlot1.png",dpi=(640/8))
        Fig3=0
        
    figure(4)
    subplot(211)
    plot(Dx,Dmeas,xd2,yd2,linewidth=2);grid()
    legend(('Initial Profile','Smoothed Profile'),'upper right')
    title('Bathymetry-Smoothing Factor='+str(SmoothParameter),size='large',weight='bold')
    ylabel('Depth [m]',weight='bold')
    
    subplot(212)
    plot(xd[0:DeepLoc],yd[0:DeepLoc],xd[0:DeepLoc],yd[0:DeepLoc]*0,'k',xd[0:DeepLoc],yd[0:DeepLoc]*0+HT-MSL,'-.k',linewidth=2);grid()
    xlabel('Cross-Shore Distance [m]',weight='bold')
    ylabel('Elevation [m]',size='large')
    title('Foreshore and Backshore',size='large',weight='bold')
    savefig(html_txt+"ProfilePlot2.png",dpi=(640/8))
    
elif BackHelp==2 or BackHelp==3:
    figure(2)
    plot(xd,yd,xd,yd*0,'k',xd,yd*0-MSL,'--k',xd,yd*0+HT-MSL,'-.k',linewidth=2);grid()
    legend(('Bathymetry Profile','Mean Sea Level','Mean Low Water','Mean High Water'),'upper right')
    ylabel('Depth [m]',weight='bold')
    xlabel('Cross-Shore Distance [m]',weight='bold')
    title('Created Profile-Smoothing Factor='+str(SmoothParameter),size='large',weight='bold')   
    savefig(html_txt+"ProfilePlot1.png",dpi=(640/8))

    figure(3)
    plot(Dx,Dmeas,'r',xd,yd,linewidth=2);grid()
    legend(('Initial Profile','Modified Profile'),'upper right')
    ylabel('Elevation [m]',weight='bold')
    xlabel('Cross-Shore Distance [m]',weight='bold')
    savefig(html_txt+"ProfilePlot2.png",dpi=(640/8))
    Fig3=0

elif BackHelp==4:
    if ProfileQuestion=="(1) Yes":
        Dorig=num.array(Dorig);Xorig=num.array(Xorig)
        figure(2)
        plot(xd,yd,xd,yd*0,'k',xd,yd*0-MSL,'--k',xd,yd*0+HT-MSL,'-.k',linewidth=2);grid()
        ylabel('Depth [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        title('Created Profile-Smoothing Factor='+str(SmoothParameter),size='large',weight='bold')
        savefig(html_txt+"ProfilePlot1.png",dpi=(640/8));Fig2=1

        figure(3)
        subplot(211)
        plot(Dx,Dmeas,'r',xd2,yd,linewidth=2);grid()
        legend(('Initial Profile','Smoothed Profile'),'upper right')
        title('Bathymetry',size='large',weight='bold')
        ylabel('Depth [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')

        subplot(212)
        plot(Xorig,Dorig[::-1],Xorig,Dorig*0,'k',linewidth=2);grid()
        ylabel('Elevation [m]',size='large',weight='bold')
        title('Elevation seaward and landward of chosen location',size='large',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        savefig(html_txt+"ProfilePlot2.png",dpi=(640/8));Fig2=1
        Fig3=0 
        
    elif ProfileQuestion=="(2) No,but I will upload a cross-shore profile":
        figure(2)
        plot(xd,yd,xd,yd*0,'k',xd,yd*0-MSL,'--k',xd,yd*0+HT-MSL,'-.k',linewidth=2);grid()
        legend(('Bathymetry Profile','Mean Sea Level','Mean Low Water','Mean High Water'),'upper right')
        ylabel('Depth [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        title('Created Profile-Smoothing Factor='+str(SmoothParameter),size='large',weight='bold')
        savefig(html_txt+"ProfilePlot1.png",dpi=(640/8));Fig2=1

        figure(3)
        plot(Dx,Dmeas,xd,yd,xd,yd*0,'k',linewidth=2);grid()
        ylabel('Elevation [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        savefig(html_txt+"ProfilePlot2.png",dpi=(640/8))
        Fig3=0

    elif ProfileQuestion=="(3) No,please create a theoretical profile for me":
        figure(3)
        plot(xd,yd,xd,yd*0,'k',xd,yd*0-MSL,'--k',xd,yd*0+HT-MSL,'-.k',linewidth=2);grid()
        legend(('Bathymetry Profile','Mean Sea Level','Mean Low Water','Mean High Water'),'upper right')
        ylabel('Depth [m]',weight='bold')
        xlabel('Cross-Shore Distance [m]',weight='bold')
        title('Created Profile',size='large',weight='bold')
        savefig(html_txt+"ProfilePlot1.png",dpi=(640/8))
        Fig2=0;  Fig3=0


if ProfileQuestion=="(1) Yes":
    def pst(a):
        if sum(a)<>0:
            b=1
        else:
            b=0
        return b
    try:
        temp=pst(begMGx)+pst(begMRx)+pst(begCRx)+pst(begDNx)+pst(begSGx)+pst(begOTx);temp=sum(temp)
    except:
        temp=0
        
    if temp<>0:
        figure(6);j=1
        if pst(begMGx)<>0:
            subplot(temp,1,j); temp1=TempY+nan
            la=num.nonzero(MG);temp1[la]=TempY[la]
            plot(TempX,TempY,TempX,temp1,'xg');grid();
            ylabel('Mangrove Field');j=j+1
            
        if pst(begDNx)<>0:
            subplot(temp,1,j);temp1=TempY+nan
            la=num.nonzero(DN);temp1[la]=TempY[la]
            plot(TempX,TempY,TempX,temp1,'xg');grid();
            ylabel('Sand Dunes');j=j+1

        if pst(begMRx)<>0:
            subplot(temp,1,j);temp1=TempY+nan
            la=num.nonzero(MR);temp1[la]=TempY[la]
            plot(TempX,TempY,TempX,temp1,'xg');grid();
            ylabel('Marsh');j=j+1

        if pst(begSGx)<>0:
            subplot(temp,1,j);temp1=TempY+nan
            la=num.nonzero(SG);temp1[la]=TempY[la]
            plot(TempX,TempY,TempX,temp1,'xg');grid();
            ylabel('Seagrass Bed');j=j+1
               
        if pst(begCRx)<>0:
            subplot(temp,1,j);temp1=TempY+nan
            la=num.nonzero(CR);temp1[la]=TempY[la]
            plot(TempX,TempY,TempX,temp1,'xg');grid();
            ylabel('Coral Reef');j=j+1
        xlabel('Cross-Shore Distance [m]',weight='bold')

        if pst(begOTx)<>0:
            subplot(temp,1,j); temp1=TempY+nan
            la=num.nonzero(OT);temp1[la]=TempY[la]
            plot(TempX,TempY,TempX,temp1,'xg');grid();
            ylabel('Other Habitat');j=j+1
        savefig(html_txt+"ProfilePlot6.png",dpi=(640/8))
        Fig6=1               


# fetch and wind rose plots
if FetchQuestion=='(1) Yes':
    # plot fetch on rose    
    radians=(num.pi/180.0)
    pi=num.pi
    theta16=[0*radians,22.5*radians,45*radians,67.5*radians,90*radians,112.5*radians,135*radians,157.5*radians,180*radians,202.5*radians,225*radians,247.5*radians,270*radians,292.5*radians,315*radians,337.5*radians]
    rc('grid',color='#316931',linewidth=1,linestyle='-')
    rc('xtick',labelsize=0)
    rc('ytick',labelsize=15)
    # force square figure and square axes looks better for polar,IMO
    width,height=matplotlib.rcParams['figure.figsize']
    size=min(width,height)
    # make a square figure
    fig1=plt.figure()
    ax=fig1.add_axes([0.1,0.1,0.8,0.8],polar=True,axisbg='w')
    # plot
    bars=ax.bar(theta16,FetchList,width=.35,color='#ee8d18',lw=1)
    for r,bar in zip(FetchList,bars):
        bar.set_facecolor(cm.YlOrRd(r/10.))
        bar.set_alpha(.65)
    ax.set_rmax(max(FetchList)+1)
    grid(True)
    ax.set_title("Average Fetch (meters)",fontsize=15,weight='bold')
    plt.savefig(Fetch_Plot,dpi=(640/8))

if WW3_Pts:
    # modify 'Wi10' list so it conforms to rose order
    Wi10List=[]
    for i in range(3,-1,-1):
        Wi10List.append(Wi10[i])
    for i in range(len(dirList)-1,3,-1):
        Wi10List.append(Wi10[i])
    # plot wind on rose    
    radians=(num.pi/180.0)
    pi=num.pi
    theta16=[0*radians,22.5*radians,45*radians,67.5*radians,90*radians,112.5*radians,135*radians,157.5*radians,180*radians,202.5*radians,225*radians,247.5*radians,270*radians,292.5*radians,315*radians,337.5*radians]
    rc('grid',color='#316931',linewidth=1,linestyle='-')
    rc('xtick',labelsize=0)
    rc('ytick',labelsize=15)
    # force square figure and square axes looks better for polar,IMO
    width,height=matplotlib.rcParams['figure.figsize']
    size=min(width,height)
    # make a square figure
    fig1=plt.figure()
    ax=fig1.add_axes([0.1,0.1,0.8,0.8],polar=True,axisbg='w')
    # plot
    bars=ax.bar(theta16,Wi10List,width=.35,color='#ee8d18',lw=1)
    for r,bar in zip(Wi10List,bars):
        bar.set_facecolor(cm.YlOrRd(r/10.))
        bar.set_alpha(.65)
    ax.set_rmax(max(Wi10List)+1)
    grid(True)
    ax.set_title("Wind Speed (meters/second)",fontsize=15,weight='bold')
    plt.savefig(Wind_Plot,dpi=(640/8))

# create txt profile for created portion
file=open(CreatedProfile,"w")
for i in range(0,len(yd)):
    file.writelines(str(xd[i])+"\t"+str(yd[i])+"\n")
file.close()

# return projected point to geographic (unprojected)
gp.Project_management(LandPoint,LandPoint_Geo,geo_projection)
# grab coordinates for Google Maps plot
cur=gp.UpdateCursor(LandPoint_Geo)
row=cur.Next()
feat=row.Shape
midpoint1=feat.Centroid
midList1=shlex.split(midpoint1)
midList1=[float(s) for s in midList1]
del cur,row
PtLat=str(round(midList1[1],4))
PtLong=str(round(midList1[0],4))
TR=str(HT)

WaveClimateCheck=0


# create html files
htmlfile=open(Profile_HTML,"w")
htmlfile.write("<html><title>Marine InVEST - Profile Generator</title><CENTER><H1>Coastal Protection - Tier 1</H1><H2>Profile Generator Results ("+subwsStr+")<br></H2><p>")
htmlfile.write("[ PROFILE INFO ]<br><a href=\"fetchwindwave.html\">[ FETCH, WAVE, AND WIND INFO ]</a><br>")
htmlfile.write("<CENTER><br><HR>")
htmlfile.write("<table border=\"0\" width=\"800\" cellpadding=\"5\" cellspacing=\"20\"><tr><td>")
htmlfile.write("<iframe width=\"350\" height=\"325\" frameborder=\"0\" scrolling=\"no\" marginheight=\"0\" marginwidth=\"0\"")
htmlfile.write("src=\"http://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q=")
htmlfile.write(PtLat+","+PtLong)
htmlfile.write("&amp;aq=&amp;sspn=0.009467,0.021136&amp;vpsrc=6&amp;ie=UTF8&amp;ll=")
htmlfile.write(PtLat+","+PtLong)
htmlfile.write("&amp;spn=0.063714,0.169086&amp;t=h&amp;z=12&amp;output=embed\"></iframe>")
htmlfile.write("</td><td>")
htmlfile.write("<H2><u>Site Information</u></H2>")
htmlfile.write("The site is located at:<br><li> latitude = "+PtLat+"<br><li> longitude = "+PtLong+"<p>")
htmlfile.write("The average sediment size is: "+str(Diam)+"mm<br><p>")
if Diam > 1.1:
    htmlfile.write("<i>Your beach has coarse sand/gravel. It won't be eroded during a storm</i><p>")
elif Diam >= 0.1:
    htmlfile.write("<i>You have a sandy system.  It can be eroded during a storm</i><p>")
else:
    htmlfile.write("<i>Your systems has a lots of fines/consolidated sediments. It is not an erodible beach</i><p>")
htmlfile.write("The tidal range is: "+TR+"m (high tide value)<br>")
if HT < 2:
    htmlfile.write("Your site is microtidal (Tidal Range < 2m)<br>")
elif HT <= 4:
    htmlfile.write("Your site is meso-tidal (2 <= Tidal Range <= 4m)<br>")
else:
    htmlfile.write("Your site is macro-tidal (Tidal Range > 4m)<br>")
htmlfile.write("</td></tr></table>")


# backshore information
if BackHelp==1:
    htmlfile.write("<HR><H2><u>Backshore Information for a Sandy Beach System</u></H2>")
    htmlfile.write("<table border=\"0\" width=\"1100\" cellpadding=\"5\" cellspacing=\"10\">")
    htmlfile.write("<tr><td>The figure below shows the entire smoothed profile that was created for you.")
    htmlfile.write("<img src=\"ProfilePlot1.png\" alt=\"Profile Plot #1\" width=\"640\" height=\"480\"></td>")
    htmlfile.write("<td>The figure below shows a zoom-in on the bathymetry and inter- to supratidal portions.<br>")
    htmlfile.write("<li> The top subplot shows original and smoothed bathymetry.<br><li> The bottom subplot shows a zoom-in on intertidal and backshore profiles.<br>")
    htmlfile.write("<img src=\"ProfilePlot2.png\" alt=\"Profile Plot #2\" width=\"640\" height=\"480\"></td></tr></table><br>")
    Foreshore=str(int(Slope))
    DuneH=str(round(DuneCrest,1))
    BermH=str(round(BermCrest,1))
    BermW=str(round(BermLength,1))
    htmlfile.write("Additional information about your site from your inputs:<br>")
    htmlfile.write("<li> The foreshore slope is: 1/"+Foreshore+"<br>")
    htmlfile.write("<li> The berm at your site is is: "+BermH+"m high and "+BermW+"m long<br>")
    if Tm==-1:
        htmlfile.write("We couldn't estimate a default value for dune height at your site. We assumed a default value of 2m for plotting purposes, but again we don't know if this is true at your site.<br>")
    else:
        htmlfile.write("<li> The dune at your site is is: "+DuneH+"m high<br>")
        
    htmlfile.write("<table border=\"0\" width=\"1100\" cellpadding=\"5\" cellspacing=\"10\"><tr>") 
    if Fig3==1:
        htmlfile.write("<td>")
        htmlfile.write("The figure below shows the profile that was cut from GIS,<br>including the bathymetry and topography at your location of interest.<br>")
        htmlfile.write("<img src=\"ProfilePlot3.png\" alt=\"Profile Plot #3\" width=\"640\" height=\"480\">")
        htmlfile.write("</td>")

elif BackHelp==2:
    htmlfile.write("<HR><H2><u>Backshore Information for a Mangrove/Marsh System</u></H2>")
    htmlfile.write("<table border=\"0\" width=\"1100\" cellpadding=\"5\" cellspacing=\"10\">")
    htmlfile.write("<tr><td>The figure below shows the whole smoothed profile that was created for you.<br>")
    htmlfile.write("<img src=\"ProfilePlot1.png\" alt=\"Profile Plot #1\" width=\"640\" height=\"480\"></td>")
    htmlfile.write("<td>The figure below shows a zoom-in on the bathymetry and inter- to supratidal portions.<br>")
    htmlfile.write("<li> The top subplot shows original and smoothed bathymetry.<br><li> The bottom subplot shows a zoom-in on intertidal and backshore profiles.<br>")
    htmlfile.write("<img src=\"ProfilePlot2.png\" alt=\"Profile Plot #2\" width=\"640\" height=\"480\"></td></tr></table><br>")
    htmlfile.write("Additional information about your site from your inputs:<br>")
    if abs(OffX[0]+ShoreX[0])<>0:
        htmlfile.write("<li> You have a slope of 1:"+str(SlopeM[0])+" for "+str(ShoreX[0]-OffX[0])+"m, from "+str(OffX[0])+" to "+str(ShoreX[0])+"m<br>")
    if abs(OffX[1]+ShoreX[1])<>0:
        htmlfile.write("<li> You have a slope of 1:"+str(SlopeM[1])+" for "+str(ShoreX[1]-OffX[1])+"m, from "+str(OffX[1])+" to "+str(ShoreX[1])+"m<br>")
    if abs(OffX[2]+ShoreX[2])<>0:
        htmlfile.write("<li> You have a slope of 1:"+str(SlopeM[2])+" for "+str(ShoreX[2]-OffX[2])+"m, from "+str(OffX[2])+" to "+str(ShoreX[2])+"m<br>")

elif BackHelp==3 or BackHelp==4:
    htmlfile.write("<HR><table border=\"0\" width=\"1100\" cellpadding=\"5\" cellspacing=\"10\">")
    htmlfile.write("<tr><td>")
    htmlfile.write("<img src=\"ProfilePlot1.png\" alt=\"Profile Plot #1\" width=\"640\" height=\"480\">")
    if Fig2==1:
        htmlfile.write("</td><td>")
        htmlfile.write("<img src=\"ProfilePlot2.png\" alt=\"Profile Plot #2\" width=\"640\" height=\"480\">")
    htmlfile.write("</td></tr></table>")

if Fig6: 
    htmlfile.write("<hr><H2><u>Location of Natural Habitats</u></H2>")
    htmlfile.write("<table border=\"0\" width=\"1100\" cellpadding=\"5\" cellspacing=\"10\">")
    htmlfile.write("<tr><td><img src=\"ProfilePlot6.png\" alt=\"Location of Natural Habitats\" width=\"640\" height=\"480\"></td><td>")
    htmlfile.write("You have at least one biotic or abiotic natural habitat in your area of interest.  \
                    We indicate below its type, start and end locations.  Distances are referenced in meters from the shoreline.\
                    Positive distances are oriented seaward and negative distances landward.<p>")
    if pst(begMGx)<>0:
        htmlfile.write("You have a mangrove field that starts and ends at the locations indicated below:<br>")
        B=begMGx;F=finMGx
        htmlfile.write("<table border=\"0\" width=\"200\" cellpadding=\"0\" cellspacing=\"0\"><tr>")
        htmlfile.write("<td> </td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(kk)+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>Start [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(B[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>End [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(F[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("</table>")
        htmlfile.write("<p>")
        
    if pst(begDNx)<>0:
        htmlfile.write("You have a dune field that starts and ends at the locations indicated below:<br>")
        B=begDNx;F=finDNx
        htmlfile.write("<table border=\"0\" width=\"200\" cellpadding=\"0\" cellspacing=\"0\"><tr>")
        htmlfile.write("<td> </td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(kk)+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>Start [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(B[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>End [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(F[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("</table>")
        htmlfile.write("<p>")
        
    if pst(begSGx)<>0:
        htmlfile.write("You have a seagrass bed that starts and ends at the locations indicated below:<br>")
        B=begSGx;F=finSGx
        htmlfile.write("<table border=\"0\" width=\"200\" cellpadding=\"0\" cellspacing=\"0\"><tr>")
        htmlfile.write("<td> </td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(kk)+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>Start [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(B[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>End [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(F[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("</table>")
        htmlfile.write("<p>")
        
    if pst(begCRx)<>0:
        htmlfile.write("You have a coral reef that starts and ends at the locations indicated below:<br>")
        B=begCRx;F=finCRx
        htmlfile.write("<table border=\"0\" width=\"200\" cellpadding=\"0\" cellspacing=\"0\"><tr>")
        htmlfile.write("<td> </td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(kk)+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>Start [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(B[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>End [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(F[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("</table>")
        htmlfile.write("<p>")
        
    if pst(begMRx)<>0:
        htmlfile.write("You have a marsh that starts and ends at the locations indicated below:<br>")
        B=begMRx;F=finMRx
        htmlfile.write("<table border=\"0\" width=\"200\" cellpadding=\"0\" cellspacing=\"0\"><tr>")
        htmlfile.write("<td> </td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(kk)+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>Start [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(B[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>End [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(F[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("</table>")
        htmlfile.write("<p>")
        
    if pst(begOTx)<>0:
        htmlfile.write("You have another habitat (OT) that starts and ends at the locations indicated below:<br>")
        B=begOTx;F=finOTx
        htmlfile.write("<table border=\"0\" width=\"200\" cellpadding=\"0\" cellspacing=\"0\"><tr>")
        htmlfile.write("<td> </td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(kk)+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>Start [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(B[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<td>End [m]</td>")
        for kk in range(len(B)):
            htmlfile.write("<td>"+str(F[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("</table>")
        htmlfile.write("<p>")
        
    htmlfile.write("</td></tr></table>")
htmlfile.close() # close HTML


htmlfile=open(FetchWindWave_HTML,"w")
htmlfile.write("<html><title>Marine InVEST - Profile Generator</title><CENTER><H1>Coastal Protection - Tier 1</H1><H2>Profile Generator Results ("+subwsStr+")<br></H2><p>")
htmlfile.write("<a href=\"profile.html\">[ PROFILE INFO ]</a><br>[ FETCH, WAVE, AND WIND INFO ]<br>")
htmlfile.write("<CENTER><br><HR><H2><u>Fetch and Wind Roses</u></H2></CENTER>")
htmlfile.write("<table border=\"0\" width=\"1100\" cellpadding=\"5\" cellspacing=\"0\"><tr><td>")
htmlfile.write("<iframe width=\"350\" height=\"325\" frameborder=\"0\" scrolling=\"no\" marginheight=\"0\" marginwidth=\"0\"")
htmlfile.write("src=\"http://maps.google.com/maps?f=q&amp;source=s_q&amp;hl=en&amp;geocode=&amp;q=")
htmlfile.write(PtLat+","+PtLong)
htmlfile.write("&amp;aq=&amp;sspn=0.009467,0.021136&amp;vpsrc=6&amp;ie=UTF8&amp;ll=")
htmlfile.write(PtLat+","+PtLong)
htmlfile.write("&amp;spn=0.063714,0.169086&amp;t=h&amp;z=12&amp;output=embed\"></iframe>")
htmlfile.write("</td><td>")
htmlfile.write("<img src=\"Fetch_Plot.png\" width=\"347\" height=\"260\" alt=\"Fetch Rose: No Fetch Calculation Selected\"></td><td>")
htmlfile.write("<img src=\"Wind_Plot.png\" width=\"347\" height=\"260\" alt=\"Wind Rose: No Wave Watch III Info Provided\"></td></tr></table>")

if WW3_Pts or FetchQuestion=='(1) Yes':
    htmlfile.write("<HR><H2><u>Wind and Wave Information</u></H2>")
    
    if WW3_Pts:
        htmlfile.write("<i>From Wave Watch III data, we estimated various wind speed values<br>that we used to generate waves from each of the 16 fetch directions.</i><br>")
    htmlfile.write("<table border=\"1\" width=\"900\" cellpadding=\"6\" cellspacing=\"0\"><tr>")
    htmlfile.write("</td><th colspan=\"1\"></th><th colspan=\"16\"><b>Direction (degrees)</b></th></tr>")
    htmlfile.write("<tr align=\"center\"><td></td>")
    for kk in range(0,16):
        htmlfile.write("<td><b>"+str(dirList[kk])+"�</b></td>")
    htmlfile.write("</tr><tr align=\"center\"><td><b>Fetch (km)</b></td>")
    
    if FetchQuestion=='(1) Yes':
        for kk in range(0,16):
            htmlfile.write("<td>"+str(int(FetchFinalList[kk]))+"</td>")
    else:
        for kk in range(0,16):
            htmlfile.write("<td>-</td>")
    if WW3_Pts:
        htmlfile.write("</tr>")
        htmlfile.write("<tr align=\"center\"><td><b><FONT COLOR=\"980000\">Max Wind Speed (m/s)</FONT></b></td>")
        for kk in range(0,16):
            htmlfile.write("<td>"+str(WiMax[kk])+"</td>")
            
    if WW3_Pts and FetchQuestion=='(1) Yes':
        htmlfile.write("</tr>")
        htmlfile.write("<tr align=\"center\"><td><b>Wave Height (m)</b></td>")
        for kk in range(0,16):
            temp1=round(WiWavMax[kk],2)
            if temp1==0.0:
                temp1=0 
            htmlfile.write("<td>"+str(temp1)+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<tr align=\"center\"><td><b>Wave Period (s)</b></td>")
        for kk in range(0,16):
            temp2=round(WiPerMax[kk],2)
            if temp2==0.0:
                temp2=0     
            htmlfile.write("<td>"+str(temp2)+"</td>")
            
    if WW3_Pts:            
        htmlfile.write("</tr>")
        htmlfile.write("<tr align=\"center\"><td><b><FONT COLOR=\"C80000\">Top 10% Wind Speed (m/s)</FONT></b></td>")
        for kk in range(0,16):
            htmlfile.write("<td>"+str(Wi10[kk])+"</td>")
        htmlfile.write("</tr>")
        htmlfile.write("<tr align=\"center\"><td><b><FONT COLOR=\"FF0000\">Top 25% Wind Speed (m/s)</FONT></b></td>")
        for kk in range(0,16):
            htmlfile.write("<td>"+str(Wi25[kk])+"</td>")
    htmlfile.write("</tr></table><p>")
    
    if WW3_Pts and FetchQuestion=='(1) Yes':
        htmlfile.write("<u>Summary</u>:<br>")
        temp=[WiPerMax[ii]*WiWavMax[ii]**2 for ii in range(len(WiPerMax))];loc=argmax(num.array(temp))
        htmlfile.write("<li> The most powerful wave generated by the maximum wind speed is: Ho="+str(round(WiWavMax[loc],2))+"m, with a period of To="+str(round(max(WiPerMax),2))+"<br>")
        temp=[WiPer10[ii]*WiWav10[ii]**2 for ii in range(len(WiPer10))];loc=argmax(num.array(temp))
        htmlfile.write("<li> The most powerful wave generated by the top 10% wind speed is: Ho="+str(round(WiWav10[loc],2))+"m, with a period of To="+str(round(max(WiPer10),2))+"<br>")
        temp=[WiPer25[ii]*WiWav10[ii]**2 for ii in range(len(WiPer25))];loc=argmax(num.array(temp))
        htmlfile.write("<li> The most powerful wave generated by the top 25% wind speed is: Ho="+str(round(WiWav25[loc],2))+"m, with a period of To="+str(round(max(WiPer25),2))+"s<p><br>")
else:
    htmlfile.write("<li> We cannot provide you with wave information at your site since you didn't include Wave Watch III in the analysis.<p>")

    if WW3_Pts:
        htmlfile.write("<b>Wave Height Data from Wave Watch III </b></br>")
        htmlfile.write("<i>From WaveWatchIII data, we estimated various <br>wave height/period values that you could use as input into the wave model</i>")
        htmlfile.write("<table border=\"1\" width=\"600\" cellpadding=\"6\" cellspacing=\"0\">")
        htmlfile.write("<tr align=\"center\"></td><th colspan=\"1\"></th><td>Wave Height (m)</td><td>Wave Period (m)</td></tr><tr align=\"center\">")
        htmlfile.write("<td><b>Maximum Wave</b></td>")
        htmlfile.write("<td>"+str(WavMax[0])+"</td>")
        htmlfile.write("<td>"+str(WavMax[1])+"</td>")
        htmlfile.write("</tr><tr align=\"center\">")
        htmlfile.write("<td><b>Top 10% Wave</b></td>")
        htmlfile.write("<td>"+str(Wav10[0])+"</td>")
        htmlfile.write("<td>"+str(Wav10[1])+"</td>")
        htmlfile.write("</tr><tr align=\"center\">")
        htmlfile.write("<td><b>Top 20% Wave</b></td>")
        htmlfile.write("<td>"+str(Wav25[0])+"</td>")
        htmlfile.write("<td>"+str(Wav25[1])+"</td>")
        htmlfile.write("</tr><tr align=\"center\">")
        htmlfile.write("<td><b>10 Year Wave</b></td>")
        htmlfile.write("<td>"+str(Wav10yr)+"</td>")
        htmlfile.write("<td>-</td>")
        htmlfile.write("</tr>")
        if Tm<>-1:
            htmlfile.write("<tr align=\"center\"><td><b>Most Frequent</b></td>")
            htmlfile.write("<td>"+str(Hm)+"</td>")
            htmlfile.write("<td>"+str(Tm)+"</td>")
        htmlfile.write("</table>")
    else:
        htmlfile.write("We cannot provide you with wave information at your site since you didn't include Wave Watch III in the analysis.<br>")

htmlfile.close() # close HTML


# create parameter file
parameters.append("Script location: "+os.path.dirname(sys.argv[0])+"\\"+os.path.basename(sys.argv[0]))
parafile=open(subws+"parameters_"+now.strftime("%Y-%m-%d-%H-%M")+".txt","w") 
parafile.writelines("PROFILE GENERATOR PARAMETERS\n")
parafile.writelines("____________________________\n\n")
     
for para in parameters:
    parafile.writelines(para+"\n")
    parafile.writelines("\n")
parafile.close()