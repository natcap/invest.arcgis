# Marine InVEST: Aesthetic Views Model (Viewshed Analysis)
# Authors: Gregg Verutes, Mike Papenfus
# Coded for ArcGIS 9.3 and 10
# 06/26/11

# import modules
import sys, string, os, datetime, shlex
import arcgisscripting
from math import *

# create the geoprocessor object
gp = arcgisscripting.create()
# set output handling
gp.OverwriteOutput = 1
# check out any necessary licenses
gp.CheckOutExtension("spatial")
gp.CheckOutExtension("management")
gp.CheckOutExtension("analysis")
gp.CheckOutExtension("conversion")

# error messages
msgArguments = "\nProblem with arguments."
msgDataPrep = "\nError in preparing data."
msgVShed = "\nError conducting viewshed and population analysis."
msgIntersect = "\nError calculating overlap between viewshed output and visual polygons."
msgNumPyNo = "NumPy extension is required to run the Aesthetic Quality model.  Please consult the Marine InVEST FAQ for instructions on how to install."
msgSciPyNo = "SciPy extension is required to run the Aesthetic Quality model.  Please consult the Marine InVEST FAQ for instructions on how to install."

# import modules
try:
    import numpy
except:
    gp.AddError(msgNumPyNo)
    raise Exception

try:
    from scipy import stats
except:
    gp.AddError(msgSciPyNo)
    raise Exception

try:
    try:
        # get parameters
        parameters = []
        now = datetime.datetime.now()
        parameters.append("Date and Time: "+ now.strftime("%Y-%m-%d %H:%M"))
        gp.workspace = gp.GetParameterAsText(0)
        parameters.append("Workspace: "+ gp.workspace)
        gp.scratchWorkspace = gp.GetParameterAsText(0)
        parameters.append("Scratch Workspace: "+ gp.scratchWorkspace)
        AOI = gp.GetParameterAsText(1)
        parameters.append("Area of Interest (AOI): "+ AOI)
        cellsize = gp.GetParameterAsText(2)
        if cellsize:
            cellsize = int(gp.GetParameterAsText(2))
        parameters.append("Cell Size (meters): "+ str(cellsize))
        NegPointsCur = gp.GetParameterAsText(3)
        parameters.append("Current Point Features Contributing to Negative Aesthetic Quality: "+ NegPointsCur)
        NegPointsFut = gp.GetParameterAsText(4)
        parameters.append("Future Point Features Contributing to Negative Aesthetic Quality: "+ NegPointsFut)
        DEM = gp.GetParameterAsText(5)
        parameters.append("Digital Elevation Model (DEM): "+ DEM)
        RefractCoeff = float(gp.GetParameterAsText(6))
        parameters.append("Refractivity Coefficient: "+ str(RefractCoeff))
        globalPop = gp.GetParameterAsText(7)
        parameters.append("Population Raster: "+ globalPop)
        visualPolys = gp.GetParameterAsText(8)
        parameters.append("Polygon Features for Overlap Analysis: "+ visualPolys)
    except:
        raise Exception, msgArguments + gp.GetMessages(2)

    try:
        thefolders=["intermediate","Output"]
        for folder in thefolders:
            if not gp.exists(gp.workspace+folder):
                gp.CreateFolder_management(gp.workspace, folder)
    except:
        raise Exception, "Error creating folders"

    # local variables 
    outputws = gp.workspace + os.sep + "Output" + os.sep
    interws = gp.workspace + os.sep + "intermediate" + os.sep

    DEM_1_rc = interws + "DEM_1_rc"
    DEM_2poly = interws + "DEM_2poly.shp"
    AOI_lyr = interws + "AOI_buff_lyr.lyr"
    DEM_2poly_lyr = interws + "DEM_2poly_lyr.lyr"
    DEM_land = interws + "DEM_land"
    DEM_sea = interws + "DEM_sea"
    DEM_sea_rc = interws + "DEM_sea_rc"
    DEM_vs = interws + "DEM_vs"
    vshed_cur = interws + "vshed_cur"
    vshed_fut = interws + "vshed_fut"
    vshed_rcc = interws + "vshed_rcc"
    vshed_rcf = interws + "vshed_rcf"
    vp_inter = interws + "vp_inter.shp"
    vp_inter_lyr = interws + "vp_inter.lyr"
    vp_inter2 = interws + "vp_inter2.shp"
    AOI_geo = interws + "AOI_geo.shp"
    pop_prj = interws + "pop_prj"
    zstatsPop_cur = interws + "zstatsPop_cur.dbf"
    zstatsPop_fut = interws + "zstatsPop_fut.dbf"
    zstats_vp_cur = interws + "zstats_vp_cur.dbf"
    zstats_vp_fut = interws + "zstats_vp_fut.dbf"

    vp_overlap_shp = outputws + "vp_overlap.shp"
    vp_ovlap_cur = outputws + "vp_ovlap_cur"
    vp_ovlap_dif = outputws + "vp_ovlap_dif"
    vshed_qualc = outputws + "vshed_qualc"
    vshed_qualf = outputws + "vshed_qualf"
    vshed_diff = outputws + "vshed_diff"
    PopHTML = outputws + "populationStats_"+now.strftime("%Y-%m-%d-%H-%M")+".html"


    ##############################################
    ###### COMMON FUNCTION AND CHECK INPUTS ######
    ##############################################
    
    def AddField(FileName, FieldName, Type, Precision, Scale):
        fields = gp.ListFields(FileName, FieldName)
        field_found = fields.Next()
        if field_found:
            gp.DeleteField_management(FileName, FieldName)
        gp.AddField_management(FileName, FieldName, Type, Precision, Scale, "", "", "NON_NULLABLE", "NON_REQUIRED", "")
        return FileName

    def getDatum(thedata):
        desc = gp.describe(thedata)
        SR = desc.SpatialReference
        if SR.Type == "Geographic":
            strDatum = SR.DatumName         
        else:
            gp.OutputCoordinateSystem = SR
            strSR = str(gp.OutputCoordinateSystem)
            gp.OutputCoordinateSystem = ""
            n1 = strSR.find("GEOGCS")
            n2 = strSR.find("PROJECTION")
            strDatum = strSR[n1:n2-1]
        return strDatum

    def ckProjection(data):
        dataDesc = gp.describe(data)
        spatreflc = dataDesc.SpatialReference
        if spatreflc.Type <> 'Projected':
            gp.AddError(data +" does not appear to be projected.  It is assumed to be in meters.")
            raise Exception
        if spatreflc.LinearUnitName <> 'Meter':
            gp.AddError("This model assumes that "+data+" is projected in meters for area calculations.  You may get erroneous results.")
            raise Exception

    def compareProjections(NegPoints, DEM):
        if gp.describe(NegPoints).SpatialReference.name <> gp.describe(DEM).SpatialReference.name:
            gp.AddError("Projection Error: "+NegPoints+" is in a different projection from the DEM input data.  The two inputs must be the same projection to conduct viewshed analysis.")
            raise Exception

    def grabProjection(data):
        dataDesc = gp.describe(data)
        sr = dataDesc.SpatialReference
        gp.OutputCoordinateSystem = sr
        strSR = str(gp.OutputCoordinateSystem)
        return strSR

    def checkCellSize(thedata):
         desc=gp.Describe(thedata)
         CellWidth = desc.MeanCellWidth
         CellHeight = desc.MeanCellHeight
         return int((CellHeight+CellWidth)/2.0)

    def getQuartiles(list):
        QrtList = []
        QrtList.append(stats.scoreatpercentile(list, 25))
        QrtList.append(stats.scoreatpercentile(list, 50))
        QrtList.append(stats.scoreatpercentile(list, 75))
        QrtList.append(stats.scoreatpercentile(list, 100))
        return QrtList

    def findNearest(array,value):
        idx=(numpy.abs(array-value)).argmin()
        return array[idx]


    ##############################################################
    ######## CHECK INPUTS, SET ENVIRONMENTS, & DATA PREP #########
    ##############################################################
    try:
        gp.AddMessage("\nChecking the inputs...")  
        # call various checking functions
        ckProjection(NegPointsCur)
        ckProjection(DEM)

        ## CHECK DATUM AND PROJECTION OF AOI
        
        compareProjections(NegPointsCur, DEM)
        if NegPointsFut:
            ckProjection(NegPointsFut) 
            compareProjections(NegPointsFut, DEM)
        
        cellsizeDEM = checkCellSize(DEM)
        if cellsize:
            if int(cellsize) < int(cellsizeDEM):
                gp.AddError("The cell size input is too small.\nThe model requires the cell size to be equal to or larger than DEM input's cell size.")
                raise Exception

        if visualPolys:
            ckProjection(visualPolys)

        if cellsize:
            gp.CellSize = int(cellsize)
        else:
            gp.CellSize = int(cellsizeDEM)

        # set environments
        gp.Extent = AOI
        gp.Mask = AOI
        
        # check that AOI intersects DEM extent
        gp.Reclassify_sa(DEM, "Value", "-1000000 100000 1", DEM_1_rc, "DATA")
        gp.RasterToPolygon_conversion(DEM_1_rc, DEM_2poly, "SIMPLIFY", "Value")
        gp.MakeFeatureLayer_management(AOI, AOI_lyr, "", "", "")
        gp.MakeFeatureLayer_management(DEM_2poly, DEM_2poly_lyr, "", "", "")
        SelectAOI = gp.SelectLayerByLocation(AOI_lyr, "INTERSECT", DEM_2poly_lyr, "", "NEW_SELECTION")
        if gp.GetCount(SelectAOI) > 0:
            pass
        else:
            gp.AddError("The extent of the input area of interest does not intersect the DEM input.\nResize the AOI to fit within the DEM's extent.")
            raise Exception 

        gp.AddMessage("\nPreparing the DEM...")     
        LandExpr = "setnull("+DEM+" < 0, "+DEM+")"
        gp.SingleOutputMapAlgebra_sa(LandExpr, DEM_land, "")
        SeaExpr = "setnull("+DEM+" >= 0, "+DEM+")"
        gp.SingleOutputMapAlgebra_sa(SeaExpr, DEM_sea, "")
        gp.Reclassify_sa(DEM, "Value", "-1000000 0 0", DEM_sea_rc, "DATA")

        # merge DEM sea with DEM land; DEM sea has been flattened to 0
        MergeExpr = "Merge("+DEM_land+","+DEM_sea_rc+")"
        gp.SingleOutputMapAlgebra_sa(MergeExpr, DEM_vs)
    except:
        raise Exception, msgDataPrep


    ###########################################################
    ############## VIEWSHED & POPULATION ANALYSIS #############
    ###########################################################
    try:
        gp.AddMessage("\nConducting the viewshed analysis...")  
        gp.Viewshed_sa(DEM_vs, NegPointsCur, vshed_cur, "1", "CURVED_EARTH", str(RefractCoeff))
        if NegPointsFut:
            gp.Viewshed_sa(DEM_vs, NegPointsFut, vshed_fut, "1", "CURVED_EARTH", str(RefractCoeff))
            # subtract future from current
            gp.SingleOutputMapAlgebra_sa("( "+vshed_fut+" - "+vshed_cur+" )", vshed_diff, "")

        # get number of points in "NegPoints"
        # conduct zonal stats for population summary
        NegPointsCountCur = gp.GetCount_management(NegPointsCur)
        gp.Reclassify_sa(vshed_cur, "VALUE", "0 1;1 "+str(NegPointsCountCur)+" 2", vshed_rcc, "DATA")
        gp.BuildRasterAttributeTable_management(vshed_rcc, "Overwrite")

        # get projection from AOI
        projection = grabProjection(AOI)
        # return projected AOI to geographic (unprojected)
        geo_projection = getDatum(AOI)
        gp.Project_management(AOI, AOI_geo, geo_projection)
        # grab latitude value of AOI polygons's centroid
        cur = gp.UpdateCursor(AOI_geo)
        row = cur.Next()
        feat = row.Shape
        midpoint = feat.Centroid
        midList = shlex.split(midpoint)
        midList = [float(s) for s in midList]
        del cur
        del row
        latValue = numpy.abs(midList[1])

        # based on centroid of AOI, calculate latitude for approximate projection cell size
        latList = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 27.5, 30.0, 32.5, 35.0, 37.5, 40.0, 42.5, 45.0, 47.5, 50.0, 52.5, 55.0, 57.5, 60.0, 62.5, 65.0, 67.5, 70.0, 72.5, 75.0, 77.5, 80.0]
        cellSizeList = [927.99, 924.39, 920.81, 917.26, 913.74, 902.85, 892.22, 881.83, 871.69, 853.83, 836.68, 820.21, 804.38, 778.99, 755.17, 732.76, 711.64, 679.16, 649.52, 622.35, 597.37, 557.69, 522.96, 492.30, 465.03, 416.93, 377.84, 345.46, 318.19, 256.15, 214.36, 184.29, 161.62]
        latList = numpy.array(latList)
        #latValue = 49.1
        latList_near = findNearest(latList,latValue)
        latList_index = numpy.where(latList==latList_near)

        # project and clip global population raster
        gp.ProjectRaster_management(globalPop, pop_prj, projection, "BILINEAR", str(cellSizeList[latList_index[0]]), "", "", "")
        
        gp.ZonalStatisticsAsTable_sa(vshed_rcc, "VALUE", pop_prj, zstatsPop_cur, "DATA")
        if NegPointsFut:
            NegPointsCountFut = gp.GetCount_management(NegPointsFut)
            gp.Reclassify_sa(vshed_fut, "VALUE", "0 1;1 "+str(NegPointsCountFut)+" 2", vshed_rcf, "DATA")
            gp.BuildRasterAttributeTable_management(vshed_rcf, "Overwrite")
            gp.ZonalStatisticsAsTable_sa(vshed_rcf, "VALUE", globalPop, zstatsPop_fut, "DATA")

        # populate vshed_cur values in list
        gp.BuildRasterAttributeTable_management(vshed_cur, "Overwrite")
        cur = gp.UpdateCursor(vshed_cur)
        row = cur.Next()
        vshedList_cur = []      
        while row:
             cellValue = row.VALUE
             cellCount = row.COUNT
             if row.VALUE > 0:
                 for i in range(0,cellCount):
                     vshedList_cur.append(cellValue)
             cur.UpdateRow(row)
             row = cur.next()
        del row
        del cur

        # populate vshed_fut values in list
        if NegPointsFut:
            gp.BuildRasterAttributeTable_management(vshed_fut, "Overwrite")
            cur = gp.UpdateCursor(vshed_fut)
            row = cur.Next()
            vshedList_fut = []      
            while row:
                 cellValue = row.VALUE
                 cellCount = row.COUNT
                 if row.VALUE > 0:
                     for i in range(0,cellCount):
                         vshedList_fut.append(cellValue)
                 cur.UpdateRow(row)
                 row = cur.next()
            del row
            del cur        

        # if future points provided, determine which max value is higher
        maxDist = 1
        if NegPointsFut:
            if max(vshedList_fut) > max(vshedList_cur):
                maxDist = 2

        # create a list for breaks (25, 50, 75, 100 Percentiles)
        gp.AddMessage("...classifying the results in quartiles")
        if maxDist == 1:
            QuartList = getQuartiles(vshedList_cur)
        else:
            QuartList = getQuartiles(vshedList_fut)
        QuartExpr = "0 0;1 "+str(int(QuartList[0]))+" 1;"+str(int(QuartList[0]))+" "+str(int(QuartList[1]))+" 2;"+str(int(QuartList[1]))+" "+str(int(QuartList[2]))+" 3;"+str(int(QuartList[2]))+" "+str(int(QuartList[3]))+" 4"
        gp.Reclassify_sa(vshed_cur, "VALUE", QuartExpr, vshed_qualc, "DATA")
        gp.BuildRasterAttributeTable_management(vshed_qualc, "Overwrite")
        vshed_qualc = AddField(vshed_qualc, "VIS_QUAL", "TEXT", "50", "0")
        vshed_qualc = AddField(vshed_qualc, "VAL_BREAKS", "TEXT", "50", "0")
        # run through "vshed_qualc" raster and add qual labels
        cur = gp.UpdateCursor(vshed_qualc, "", "", "VALUE; VIS_QUAL; VAL_BREAKS")
        row = cur.Next()
        while row:
            QualValue = int(row.GetValue("VALUE"))
            if QualValue == 0:
                row.SetValue("VIS_QUAL", "0 UNAFFECTED (No Visual Impact)")
                row.SetValue("VAL_BREAKS", "0 Sites Visible")   
            if QualValue == 1:
                row.SetValue("VIS_QUAL", "1 HIGH (Low Visual Impact)")
                row.SetValue("VAL_BREAKS", "0 < Sites Visible <= "+str(int(QuartList[0])))
            if QualValue == 2:
                row.SetValue("VIS_QUAL", "2 MEDIUM (Moderate Visual Impact)")
                row.SetValue("VAL_BREAKS", str(int(QuartList[0]))+" < Sites Visible <= "+str(int(QuartList[1])))
            if QualValue == 3:
                row.SetValue("VIS_QUAL", "3 LOW (High Visual Impact)")
                row.SetValue("VAL_BREAKS", str(int(QuartList[1]))+" < Sites Visible <= "+str(int(QuartList[2])))
            if QualValue == 4:
                row.SetValue("VIS_QUAL", "4 VERY LOW/POOR (Very High Visual Impact)")
                row.SetValue("VAL_BREAKS", str(int(QuartList[2]))+" < Sites Visible <= "+str(int(QuartList[3])))
            cur.UpdateRow(row)
            row = cur.Next()
        del cur    
        del row      
        
        if NegPointsFut:
            gp.Reclassify_sa(vshed_fut, "VALUE", QuartExpr, vshed_qualf, "DATA")
            gp.BuildRasterAttributeTable_management(vshed_qualf, "Overwrite")
            vshed_qualf = AddField(vshed_qualf, "VIS_QUAL", "TEXT", "50", "0")
            vshed_qualf = AddField(vshed_qualf, "VAL_BREAKS", "TEXT", "50", "0")
            # run through "vshed_qualc" raster and add qual labels
            cur = gp.UpdateCursor(vshed_qualf, "", "", "VALUE; VIS_QUAL; VAL_BREAKS")
            row = cur.Next()
            while row:
                QualValue = int(row.GetValue("VALUE"))
                if QualValue == 0:
                    row.SetValue("VIS_QUAL", "0 UNAFFECTED (No Visual Impact)")
                    row.SetValue("VAL_BREAKS", "0 Sites Visible")   
                if QualValue == 1:
                    row.SetValue("VIS_QUAL", "1 HIGH (Low Visual Impact)")
                    row.SetValue("VAL_BREAKS", "0 < Sites Visible <= "+str(int(QuartList[0])))
                if QualValue == 2:
                    row.SetValue("VIS_QUAL", "2 MEDIUM (Moderate Visual Impact)")
                    row.SetValue("VAL_BREAKS", str(int(QuartList[0]))+" < Sites Visible <= "+str(int(QuartList[1])))
                if QualValue == 3:
                    row.SetValue("VIS_QUAL", "3 LOW (High Visual Impact)")
                    row.SetValue("VAL_BREAKS", str(int(QuartList[1]))+" < Sites Visible <= "+str(int(QuartList[2])))
                if QualValue == 4:
                    row.SetValue("VIS_QUAL", "4 VERY LOW/POOR (Very High Visual Impact)")
                    row.SetValue("VAL_BREAKS", str(int(QuartList[2]))+" < Sites Visible <= "+str(int(QuartList[3])))
                cur.UpdateRow(row)
                row = cur.Next()
            del cur    
            del row

        # search through zonal stats table for population within current viewshed
        cur = gp.UpdateCursor(zstatsPop_cur)
        row = cur.Next()
        PopListCur = []
        while row:
             PopListCur.append(int(row.SUM))
             cur.UpdateRow(row)
             row = cur.next()
        del row
        del cur

        if NegPointsFut:
            # search through zonal stats table for population within future viewshed
            cur = gp.UpdateCursor(zstatsPop_fut)
            row = cur.Next()
            PopListFut = []
            while row:
                 PopListFut.append(int(row.SUM))
                 cur.UpdateRow(row)
                 row = cur.next()
            del row
            del cur      

        # create html file output
        htmlfile = open(PopHTML, "w")
        htmlfile.write("<html>\n")
        htmlfile.write("<title>Marine InVEST</title>")
        htmlfile.write("<center><H1>Aesthetic Quality Model</H1></center><br>")
        htmlfile.write("This page contains population results from running the Marine InVEST Aesthetic Quality Model.")
        htmlfile.write("<br><HR><H2>Population Statistics</H2><table border=\"1\", cellpadding=\"5\"><tr>")
        if NegPointsFut:
            htmlfile.write("<td align=\"center\"><b>Number of Visible Sites</b></td><td align=\"center\"><b>Current Population</b></td><td align=\"center\"><b>Future Population</b></td></tr>")
            htmlfile.write("<tr><td align=\"center\">0<br> (unaffected)</td><td align=\"center\">"+str(PopListCur[0])+"</td><td align=\"center\">"+str(PopListFut[0])+"</td>")
            htmlfile.write("<tr><td align=\"center\">1 or more<br>sites visible</td><td align=\"center\">"+str(PopListCur[1])+"</td><td align=\"center\">"+str(PopListFut[1])+"</td>")
        else:
            htmlfile.write("<td align=\"center\"><b>Number of Visible Sites</b></td><td align=\"center\"><b>Current Population</b></td><td align=\"center\"><b>Future Population</b></td></tr>")
            htmlfile.write("<tr><td align=\"center\">0<br> (unaffected)</td><td align=\"center\">"+str(PopListCur[0])+"</td>")
            htmlfile.write("<tr><td align=\"center\">1 or more<br>sites visible</td><td align=\"center\">"+str(PopListCur[1])+"</td>")
        htmlfile.write("</table>")
        htmlfile.write("</html>")
        htmlfile.close()
    except:
        raise Exception, msgVShed


    ##############################################
    ############## INTERSECT ANALYSIS ############
    ##############################################
    try:
        if visualPolys:
            gp.AddMessage("\nCalculating overlap between viewshed output and visual polygons...\n")
            gp.Select_analysis(visualPolys, vp_inter, "")
            vp_inter = AddField(vp_inter, "VALUE", "SHORT", "0", "0")  
            gp.CalculateField_management(vp_inter, "VALUE", "[FID]+1", "VB")            
    
            # add three fields
            vp_inter = AddField(vp_inter, "RateCur", "DOUBLE", "0", "0")
            if NegPointsFut:
                vp_inter = AddField(vp_inter, "RateFut", "DOUBLE", "0", "0")
                vp_inter = AddField(vp_inter, "RateDiff", "DOUBLE", "0", "0")

            gp.MakeFeatureLayer_management(vp_inter, vp_inter_lyr, "", "", "")
            gp.ZonalStatisticsAsTable_sa(vp_inter, "VALUE", vshed_qualc, zstats_vp_cur, "DATA")
            gp.AddJoin_management(vp_inter_lyr, "VALUE", zstats_vp_cur, "VALUE", "KEEP_COMMON")
            gp.CalculateField_management(vp_inter_lyr, "vp_inter.RateCur", "[zstats_vp_cur.MEAN]", "VB", "")
            gp.RemoveJoin_management(vp_inter_lyr, "zstats_vp_cur")
            
            if NegPointsFut:
                gp.ZonalStatisticsAsTable_sa(vp_inter, "VALUE", vshed_qualf, zstats_vp_fut, "DATA")
                gp.AddJoin_management(vp_inter_lyr, "VALUE", zstats_vp_fut, "VALUE", "KEEP_COMMON")
                gp.CalculateField_management(vp_inter_lyr, "vp_inter.RateFut", "[zstats_vp_fut.MEAN]", "VB", "")
                gp.RemoveJoin_management(vp_inter_lyr, "zstats_vp_fut")

            gp.FeatureClassToFeatureClass_conversion(vp_inter_lyr, interws, "vp_inter2.shp", "")
                
            if NegPointsFut:
                gp.CalculateField_management(vp_inter2, "RateDiff", "!RateCur! - !RateFut!", "PYTHON")
                gp.Select_analysis(vp_inter2, vp_overlap_shp, "NOT \"RateDiff\" = 0")
                gp.FeatureToRaster_conversion(vp_overlap_shp, "RateDiff", vp_ovlap_dif, str(int(cellsize)))
            else:
                gp.Select_analysis(vp_inter2, vp_overlap_shp, "")
                gp.FeatureToRaster_conversion(vp_inter2, "RateCur", vp_ovlap_cur, str(int(cellsize)))

    except:
        raise Exception, msgIntersect

    # create parameter file
    parameters.append("Script location: "+os.path.dirname(sys.argv[0])+"\\"+os.path.basename(sys.argv[0]))
    parafile = open(gp.workspace+"\\Output\\parameters_"+now.strftime("%Y-%m-%d-%H-%M")+".txt","w") 
    parafile.writelines("AESTHETIC QUALITY MODEL PARAMETERS\n")
    parafile.writelines("__________________________________\n\n")
         
    for para in parameters:
        parafile.writelines(para+"\n")
        parafile.writelines("\n")
    parafile.close()

    # delete superfluous intermediate data
    del1 = [AOI_lyr, DEM_2poly, DEM_2poly_lyr, DEM_1_rc, DEM_land, DEM_sea, DEM_sea_rc, vshed_rcc, vshed_rcf]
    del2 = [vp_inter_lyr, vp_inter, vp_inter2, zstatsPop_cur, zstatsPop_fut]
    deletelist = del1 + del2
    for data in deletelist:
        if gp.exists(data):
            gp.delete_management(data)
    del gp
    
except Exception, ErrorDesc:
    gp.AddMessage(gp.GetMessages())