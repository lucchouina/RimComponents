#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <sys/types.h>
/* work around warning on socket.h */
struct mmsghdr;
#include <sys/socket.h>
#include <sys/un.h>
#include <signal.h>
#include <unistd.h>
#include <syslog.h>
 
#include "trx.h"
/*
    This is the TP memory debugging framework manager,
    Check out the wiki 'trxdbg' for an overview of the framework.
*/

static int nApps=0, defaultsValid=0;
static appdata_t apps[100];

#define MAXAPPS  (sizeof(apps)/sizeof(apps[0]))

/* default can be overriden by a '*' entry in the conf file */
static appdata_t defaultAppSettings={"", FLAG_ENABLE+FLAG_POISON+FLAG_VALIDATE+FLAG_TRACK};
static appdata_t noMatchAppSettings={"", 0};

appdata_t *getAppConfig(char *name)
{
    int idx;
    
    for(idx=0;idx<nApps;idx++) {
        if(!strcmp(apps[idx].cname, name)) return &apps[idx];
    }
    trxdbg(1,0,0,"Returning %s settings for app '%s'\n", defaultsValid?"DEFAULT":"OFF", name);
    return defaultsValid?&defaultAppSettings:&noMatchAppSettings;
}

static char *conffile=TPMDBG_CONFFILE;
static int readConf()
{
FILE *fc=fopen(conffile, "r");
char buf[200];
appdata_t newapps[MAXAPPS], *app=newapps;
int n=0, line=1, error=0;

    if(!fc) {
        trxdbg(0,1,0,"Could not access configuration file %s.\n", conffile);
        trxdbg(0,0,0,"Application tracking is disabled by default.\n");
        trxdbg(0,0,1,"Use CLI to enable tracking (requires application restart).\n");
        return 0;
    }
    for(app=newapps; fgets(buf, sizeof buf -1, fc) && n<MAXAPPS; line++) {
    
        char *tok=strtok(buf, " \t\n\r");
        char *name;
        
        if(!tok) continue;
        /* parse a single line */
        
        if(tok[0]=='#') continue;
        if(strlen(tok) >= MAXCNAME) {
        
            trxdbg(0,0,0,"Line %d: Application name '%s' too long [max:%d].\n", line, tok, MAXCNAME);
            error++;
            continue;
        }
        name=tok;
        app->flags=app->tag=0;
        while((tok=strtok(NULL, " \t,\r\n"))) {

            /* parse flags : find '=', get flags name, get on/off toten, get mask value */
            char *equal;
            int32_t mask;
            
            if(!(equal=strchr(tok, '='))) {

                trxdbg(0,0,0,"Line %d: No '=' found in '%s'.\n", line, tok);
                error++;
                continue;
            }
            *equal='\0';
            if((mask=flagMask(tok)) < 0) {
            
                trxdbg(0,0,0,"Line %d: Invalid flag '%s'.\n", line, tok);
                error++;
                continue;
            }
            equal++;
            if(!strcasecmp(equal, "on")) app->flags |= mask;
            else if(strcasecmp(equal, "off")) {
            
                trxdbg(0,0,0,"Line %d: Invalid token should be on|off '%s'.\n", line, equal);
                error++;
                continue;
            }
            else app->flags &= ~mask;
        }
        trxdbg(1,0,0,"ReadConf app='%s'\n", name);
        if(!strcmp(name,"*")) {
            trxdbg(1,0,0,"Setting flags 0x%08x as default.\n", app->flags);
            defaultsValid=1;
            defaultAppSettings.flags=app->flags;
        }
        else {
            
            trxdbg(1,0,0,"Setting flags 0x%08x.\n", app->flags);
            strncpy(app->cname, name, MAXCNAME);
            app++;
            n++;
        }
    }
    if(error) {
        trxdbg(0,0,0,"%d errors detected, configuration file ignored.\n", error);
        return 0;
    }
    else {
        /* we are good to go. Copy the new config over */
        memcpy(apps, newapps, sizeof(newapps));
        nApps=n;
        return 1;
    }
}

static int redoConf=0;
static void sigHandler()
{
    trxdbg(0,0,0,"Got HUP: re-reading config.\n");
    redoConf=1;
}

void mgrShutDown()
{
    shutdownClientSocket();
    shutdownCliSocket();
}

// we make our best effort to remove the UNIX domain socket file
// else the bind() operation will fail for other users
//
static void intHandler()
{
    mgrShutDown();
}

static void setSig()
{
struct sigaction action;

    action.sa_handler=intHandler;
    action.sa_flags=SA_RESETHAND;
    sigaction(SIGINT, &action, NULL);
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGQUIT, &action, NULL);
    sigaction(SIGSEGV, &action, NULL);
    sigaction(SIGBUS, &action, NULL);
    sigaction(SIGSYS, &action, NULL);
    sigaction(SIGXFSZ, &action, NULL);
    sigaction(SIGXCPU, &action, NULL);
    sigaction(SIGXFSZ, &action, NULL);
    
    action.sa_handler=sigHandler;
    action.sa_flags=SA_RESTART;
    sigaction(SIGHUP, &action, NULL);
}

static void usage()
{
    fprintf(stderr, "usage : trxmgr [-d [-d [ ...]] [ -c <confFile>]\n");
    fprintf(stderr, "        -d incremenst debug verbosity\n");
    fprintf(stderr, "        Default <confFile> is %s\n", TPMDBG_CONFFILE);
}

int main(int argc, char **argv)
{
int c;
extern char *optarg;
extern int syslogOn;
        
    setSig();
    setupClientSocket();
    setupCliSocket();
    openlog("trx", LOG_PID, LOG_USER);
    syslogOn=1;
    // parse command line arguments
    while ((c = getopt(argc, argv, "dc:")) != EOF) {
        switch (c) {
            case 'd':
                dbgsetlvl(dbggetlvl()+1);
            break;
            case 'c':
                conffile=optarg;
            break;
            default :  case '?':
                usage();
        }
    }   
    
    if (!readConf() ) 
        trxdbg(0,0,1,"found no config - exiting.\n");
    
    if(!dbggetlvl()) {
        int pid;
        if((pid=fork())) {
            if(pid<0) trxdbg(0,1,1,"Fork failed.\n");
            exit(0);
        }
    }
    
    trxdbg(0,0,0,"Trxmgr started.\n");
    while(1) {
    
    
        fd_set fdset;
        int maxfd=0, n;
        struct timeval tv={ tv_sec: 1 };

        FD_ZERO(&fdset);
        maxfd=clientSetFds(&fdset, maxfd);
        maxfd=cliSetFds(&fdset, maxfd);
        if((n=select(maxfd+1, &fdset, 0, 0, &tv))>0) {

            clientProcessFds(&fdset);
            cliProcessFds(&fdset);
        }
        else if(n<0) {

            if(errno != EINTR) {

                trxdbg(0,1,1,"Select failed");
            }
            else {
                trxdbg(1,0,0,"Select was interupted.\n");
                if(redoConf) {

                    readConf();
                    redoConf=0;
                }
            }
        }
    }
    return 0;
}
