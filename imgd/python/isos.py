
from select import *
import rim
import os
import sys
import time
import rim
import glob
import imp

dataDir=rim.Rim().dataDir
mountRoot="/pivot%s/mnt" % dataDir
isoDir="/pivot%s/isos" % dataDir

#
# class to handle select operations
#
class isos():
    
    def __init__(self):
        self.handlers={}
        self.log=rim.logger("isos").log
        prefix="%s/img/isohandlers" % sys.path[0]
        for infile in sorted(glob.glob('%s/*.py' % prefix)):
    
            # skip over any python package management files
            if os.path.basename(infile)[0:2] == "__": continue
            fname = os.path.basename(infile)[:-3]
            mod=imp.load_source(fname, infile) 
            if 'probe' in dir(mod):
                self.handlers[fname]=mod

    def getImgList(self):
        enumStr=""
        try:
            listing = os.listdir(isoDir)
        except:
            listing = []
        sep=""
        for fname in listing:
            if len(fname) > 4:
                if fname[-4:]=='.iso':
                    enumStr='%s%s"%s"' % (enumStr,sep, fname[:-4])
                    sep=","
        return enumStr
                
    #
    # probe an iso to match it against its corresponding iso handler
    #
    def probe(self, name):
        mntpt="%s/%s" % (mountRoot, name)
        for name in self.handlers:
            handler=self.handlers[name].probe(mntpt)
            if handler:
                return handler
        return None
