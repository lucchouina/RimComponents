copyright = 'Copyright (c) 2007 TruePosition Inc.'
website = 'www.truepoisition.com'
author = 'Michael Becker'
author_email = 'mbecker@truepositon.com'
maintainer = author
maintainer_email = author
short_desc = 'uses a debugger to get symbol information from addresses'
long_desc = """pexpect script that uses a debugger to get symbol information from the addresses as
output by tpMdbg http://tpwiki/index.php/tpMdbg"""

import sys,getopt
try:
    import pexpect
except:
    print "pexpect module required. http://www.noah.org/wiki/Pexpect http://pexpect.sourceforge.net/"
    sys.exit()

def translate(address,child):
    input='whereis -a '+address
    child.sendline(input)
    child.expect('dbx')
    retval=child.before.split('\n')[1]
    if "No symbolic information available for address" in retval:
        retval="No symbolic information available for address "+address[2:]
    elif '`' in retval:
        retval=retval.split('`')[-1]
    return retval

def translateReport(filename, process):
    r=open(filename,'r')
    report=r.read()
    r.close()
    cmd = "/usr/bin/env dbx "+process
    c=pexpect.spawn(cmd)
    c.expect('dbx')
    try:
        while '0x' in report:
            beg=report.find('0x')
            end=report.find(' ',beg)
            print report[beg:end],'\r',
            t=translate(report[beg:end],c)
            report=report.replace(report[beg:end],t)
    except:
        donothing=0
    outfilename=filename+'.trans'
    of=open(outfilename,'w')
    of.write(report)
    of.close()
    c.terminate(force=True)

def usage():
        print "Usage:\t"+sys.argv[0],'[-h] path_to_executable input_file'
        print "\t-h --help print this help message"

def parseopts(iargs):
    iopts="h"
    longopts=["help"]
    opts=[]
    args=[]
    try:
        opts, args = getopt.getopt(iargs,iopts,longopts)
    except getopt.GetoptError, err:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    if len(args)!=2:
        usage()
        sys.exit(2)
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
    return args

def main():
    args=parseopts(sys.argv[1:])
    translateReport(args[1],args[0])

if __name__ == '__main__':
    main()
