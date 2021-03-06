# Marine InVEST: Fetch Tools
# Author: David Finlayson
# Coded for ArcGIS 9.3 and 10 by Gregg Verutes
# 04/25/11

import os

class fetchGeoprocessor:
    """ Contains functions that simplify calls to the real geoprocessor """
    def __init__(self, gp):
        self.gp = gp          # geoprocessing object
        self.assigned = 0     # id of assigned temp filenames
                    
    def clipToGrid(self, inGrid, outGrid, clipGrid):
        """ Clips a grid to the size of another (smaller) grid """
        # Get the clip raster extent
        desc = self.gp.Describe(clipGrid)
        extent = desc.Extent
        self.gp.Clip_management(inGrid, extent, outGrid, inGrid)

    def deleteFloat(self, inFloat):
        """ permanently deletes a Float binary file if it exists on disk """
        if os.path.exists(inFloat):
            os.remove(inFloat)
            os.remove(inFloat[:-3] + "hdr")

    def deleteGrid(self, inGrid):
        """ permanently deletes a grid if it exists on disk """
        if self.gp.Exists(inGrid):
            self.gp.Delete(inGrid)

    def findGridCenter(self, inGrid):
        """ returns the center of a grid """
        #Get the raster extent (Xmin, Ymin, Xmax, Ymax)
        desc = self.gp.Describe(inGrid)
        extent = desc.Extent
        extent = [float(i) for i in extent.split()]

        # Find the center of the GRID
        x = extent[0] + (extent[2] - extent[0])/2.0
        y = extent[1] + (extent[3] - extent[1])/2.0
        center = "%14f %14f" % (x, y)
        center = center.strip()
        return(center)

    def floatToRaster(self, inFloat, outRaster):
        """ converts a floating point binary file to a GRID """
        self.gp.FloatToRaster_conversion(inFloat, outRaster)

    def rasterToFloat(self, inRaster, outFloat):
        """ converts a GRID to a floating point binary file """
        self.gp.RasterToFloat_conversion(inRaster, outFloat)

    def rotateGrid(self, inGrid, outGrid, Angle, pivot=None):
        """ rotates a grid about a pivot point (default pivot = center of grid)"""
        # If no pivot point is given, use the center of the grid
        if pivot == None:
            pivot = self.findGridCenter(inGrid)        
        self.gp.Rotate_management(inGrid, outGrid, str(Angle % 360.0), pivot, "NEAREST")            
        return(pivot)

    def tempFloat(self):
        """ returns a unique temporary floating point binary file name """
        while True:
            self.assigned = self.assigned + 1
            dataname = "temp" + str(self.assigned).zfill(3) + ".flt"
            datapath = os.path.join(self.gp.Scratchworkspace, dataname)

            headername = "temp" + str(self.assigned).zfill(3) + ".hdr"
            headerpath = os.path.join(self.gp.Scratchworkspace, headername)

            if not os.path.exists(datapath) or not os.path.exists(headerpath):
                break
        return(datapath)

    def tempGrid(self):
        """ returns a unique temporary grid name """
        while True:
            self.assigned = self.assigned + 1
            filename = "temp" + str(self.assigned).zfill(3)
            fullpath = os.path.join(self.gp.Scratchworkspace, filename)

            if not self.gp.Exists(fullpath):
                break
        self.assigned = self.assigned + 1
        return(fullpath)
