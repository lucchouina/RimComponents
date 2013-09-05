# standard rim linkage...
Import('env')
import Rim
rim=Rim.Rim(env)

mgrSrc="""
    trxmgr.c
    trxmgrClient.c 
    trxmgrCli.c
    trxmgrRl.c
    trxmgrHist.c 
    trxTree.c
""".split()

libSrc="""
    trxlib.c 
    trxclient.c
""".split()

commonSrc="""
    trxcommon.c
""".split()

rim.addLibs("""
    ncurses
    pthread
    dl
""".split())

rim.addCflags("-O0 -g -Wall -Werror")

rim.Program("trxmgr", mgrSrc+commonSrc)

rim.SharedLib("trx", libSrc+commonSrc)
