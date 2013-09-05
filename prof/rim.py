# standard rim linkage...
Import('env')
import Rim
rim=Rim.Rim(env)
subDirs = """
    track
""".split()
rim.subdirs(subDirs)
sourceTrees={}
sourceTrees["dbg"]=subDirs
