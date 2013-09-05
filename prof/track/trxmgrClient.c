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
#include <fcntl.h>
#include <sys/ipc.h>
#include <sys/shm.h>

#ifndef __linux__
#include <procfs.h>
#endif

#include "trx.h"
#define setfd(fd) if(fd >= 0) { if(fd>maxfd) maxfd=fd; FD_SET(fd, fdset); }

typedef struct cdata_s {

    int fd;
    int pid;                    /* preserve for SIGUSR2 */
    int total;                  /* used during summary report */
    int needConfig;             /* set when client registers and we need to send config */
    int produceFinalReport;     /* set when client finished report and we need to display it */
    int more;                   /* How much data in the report */
    int reportTo;               /* What cli client wants that report */
    int subCmd;                 /* What to do with the report */
    char *pmore;                /* Report data */
    char *name;                 /* program name */
    uint32_t seq;               /* for message sequencing */
    appdata_t *adata;
    void *snap;
    int snapsize;
    
} cdata_t;

static cdata_t clients[100];
extern int summary;

int clientsPid(int idx) { return clients[idx].pid; }

#define MAXCLIENTS  (sizeof(clients)/sizeof(clients[0]))

static void closeClient(int idx)
{
    trxdbg(1,0,0,"Mgr closing client connection idx %d fd %d\n", idx, clients[idx].fd);
    if(clients[idx].reportTo>=0) cliDecWait(clients[idx].reportTo);
    close(clients[idx].fd);
    clients[idx].fd=-1;
    free(clients[idx].name);
}

static void getCmdStr(int idx, int pid)
{
  char buf[32];
  char prog_name[MAXCNAME];
#ifdef __linux__

    FILE *f;
    char line[100];
    snprintf(buf, sizeof buf, "/proc/%ld/status", (long)pid);
    if((f=fopen(buf, "r"))) {
    
        while(fgets(line, sizeof line, f)) {
        
            if(strstr(line, "Name:")) {
                char *tok=strtok(line, "\t \n\r");
                if(tok) {
                
                    if((tok=strtok(NULL, "\t \n\r"))) {
                        strncpy(prog_name, tok, sizeof prog_name);
                        fclose(f);
                        goto gotit;
                    }
                }
            }
        } 
        fclose(f);
    }
#else

    int fd;
    psinfo_t psbuf;
    snprintf(buf, sizeof buf, "/proc/%ld/psinfo", (long)pid);
    if ((fd = open(buf, O_RDONLY)) != -1)
    {
        if (read(fd, &psbuf, sizeof(psbuf)) == sizeof(psbuf)) 
        {
            char *p=prog_name;
            snprintf(prog_name, sizeof prog_name, "%s", psbuf.pr_fname);
            while(*p) {  /* remove the .unwrapped or other extensions */
                if(*p=='.') { 
                    *p='\0'; 
                    break; 
                } 
                p++;
            }
            close(fd);
            goto gotit;
        }
        close(fd);
    }
  
#endif

    snprintf(prog_name, sizeof prog_name, "%s_%d", "unknown", pid);
    
gotit:
    clients[idx].adata=getAppConfig(prog_name);
    clients[idx].pid=pid;
    clients[idx].name=strdup(prog_name);
    trxdbg(1,0,0,"Client '%s' pid %d registered.\n", prog_name, pid);
}

int getClientVsize(int idx)
{
  char buf[32];
#ifdef __linux__

    FILE *f;
    snprintf(buf, sizeof buf, "/proc/%ld/statm", (long)clients[idx].pid);
    if((f=fopen(buf, "r"))) {
        int size;
        while(fscanf(f, "%d", &size) ==1) {
            fclose(f);
            return size;
        } 
        fclose(f);
    }
#else

    int fd;
    psinfo_t psbuf;
    snprintf(buf, sizeof buf, "/proc/%ld/psinfo", (long)clients[idx].pid);
    if ((fd = open(buf, O_RDONLY)) != -1)
    {
        if (read(fd, &psbuf, sizeof(psbuf)) == sizeof(psbuf)) 
        {
            close(fd);
            return psbuf.pr_size;
        }
        close(fd);
    }
  
#endif
    return 0;
}

/* Common function for sending from Mgr to client.
*/

static int mgrSendCmd2(int idx, int cmd, int aux1, int aux2)
{
int ackval;

    trxdbg(1,0,0,"Mgr sending cmd %d to client %d pid %d\n", cmd, idx, clients[idx].pid);
    if(sendCmdMore(clients[idx].fd, clients[idx].seq, cmd, aux1, aux2, 0, 0, 0)) {
        if((ackval=recvAck(clients[idx].fd, &clients[idx].seq))>=0) return ackval;
    }
    // tear down this client connection
    closeClient(idx);
    return -1;
}

static int mgrSendCmd1(int idx, int cmd, int aux1)
{
    return mgrSendCmd2(idx, cmd, aux1, 0);
}


/* Cli wants us to walk the list of regsitered apps */
void trxmgrClientWalkList(int idx, void (*cb)(int idx, int client, char *name))
{
    int i;
    for(i=0;i<MAXCLIENTS;i++) {
        if(clients[i].fd>=0) (*cb)(idx, i, clients[i].name);
    }
}

/* Cli wants us to display the list of regsitered apps */
int trxmgrClientGetVar(int client, int var)
{
    if(clients[client].fd>=0)
        return mgrSendCmd2(client, CMD_GET, var, 0);
    return -1;
}

/* Cli wants us to display the list of regsitered apps */
int trxmgrClientAskReport(int client, int idx, int tag, int subCmd)
{
    int ret=-1;
    if(clients[client].fd>=0) {
        ret=mgrSendCmd2(client, CMD_REPORT, tag, 0);
        clients[client].reportTo=idx;
        clients[client].subCmd=subCmd;
    }
    return ret;
}

/* Cli wants us to display the list of regsitered apps */
int trxmgrClientAskPush(int client, int idx)
{
    if(clients[client].fd>=0) {
        return mgrSendCmd1(client, CMD_PUSH, 0);
    }
    return -1;
}

/* Cli wants us to display the list of regsitered apps */
int trxmgrClientAskPop(int client, int idx)
{
    if(clients[client].fd>=0) {
        return mgrSendCmd1(client, CMD_POP, 0);
    }
    return -1;
}

/* Cli wants us to display the list of regsitered apps */
int trxmgrClientSetVar(int client, int var, int value)
{
    if(clients[client].fd>=0) {
        return mgrSendCmd2(client, CMD_SET, var, value);
    }
    return -1;
}

/* send a client it's config info through a set of commands */
static void sendConfig(int idx)
{
int i;

    /* walk through the current settings for this client */
    for(i=0; i<NFLAGS; i++) {
        trxdbg(0,0,0,"Configuring embedded trx thread for client '%s'!\n", clients[idx].name);
        if(flgmap[i].mask & clients[idx].adata->flags) {
            if(mgrSendCmd2(idx, CMD_SET, flgmap[i].cmd, 1) < 0) return;
        }
        else  {
            if(flgmap[i].mask == FLAG_ENABLE) 
                trxdbg(1,0,0,"Sending DISABLE to transiant client '%s'!\n", clients[idx].name);
            if(mgrSendCmd2(idx, CMD_SET, flgmap[i].cmd, 0) < 0) return;
        }
    }
    /* let client know we are done */
    mgrSendCmd1(idx, CMD_DONE, 0);
}

static int clientRcvCB(int idx, cmd_t *cmd, int more, char *pmore)
{
    switch(cmd->cmd) {
        case CMD_REGISTER:     /* arg: pid*/
        {
            int pid;
            trxdbg(1,0,0,"Received REGISTER on idx %d pid %d.\n", idx, cmd->aux[0]);
            pid=cmd->aux[0];
            getCmdStr(idx, pid);
            clients[idx].needConfig=1;
            return 1;
        }
        break;
        case CMD_REPORT:       /* getting the report */
            /* We got the full report back */
            trxdbg(1,0,0,"Received REPORT on idx %d pid %d.\n", idx, cmd->aux[0]);
            if(!cmd->aux[0]) {
                if(summary) cliPrt(clients[idx].reportTo, "%-20s [pid %6d] [Proc Size : %6d] [Mallocated - total ->%6d - tagged -> %6d\n"
                        , clients[idx].name, clients[idx].pid, getClientVsize(idx), cmd->aux[1], 0);
                else cliPrt(clients[idx].reportTo, "Client '%s' pid %d : nothing to report.\n",clients[idx].name,clients[idx].pid);
                cliDecWait(clients[idx].reportTo);
            }
            else {
                clients[idx].more=more;
                clients[idx].pmore=pmore;
                clients[idx].produceFinalReport=1;
            }
            return 1;
        break;
        default:
            trxdbg(0,0,0,"Invalid command %d\n", cmd->cmd);
            return 0;
        break;
    }
}

static int cmpBackTraces(const void *v1,const void *v2)
{
uint32_t *t1=*(uint32_t**)v1;
uint32_t *t2=*(uint32_t**)v2, pc;

    for(pc=2; pc<MAXCALLERS+2; pc++) {
        if(*(t1+pc) < *(t2+pc)) return -1;
        else if(*(t1+pc) > *(t2+pc)) return  1;
    }
    return 0;
}

static void showReport(int idx)
{
int cliIdx=clients[idx].reportTo;
int segid;

    /* get the data from the shared memory segment and process it */
    /* send the output to the asociated cli entry as indicated by the reportTo 
       value in the cli entry clients[idx] */
    
    /*
        We need to :
        
        - find and attch to the shared memory segment
        - use the 4 words of eacg data entry to generate a btree of all entrie
        - Print the btree on the cli out
    */
    // get the shared memory segment
    trxdbg(1,0,0,"showReport : geting shm key %d\n", KEYBASE+clients[idx].pid);
    if((segid=shmget(KEYBASE+clients[idx].pid, 0, O_RDONLY)) < 0)
        trxdbg(0,1,0,"Could not open shared memory segment\n");
    else {
        void *mapaddr;
        trxdbg(1,0,0,"Found shared memory segment key %d [id=%d]\n", KEYBASE+clients[idx].pid, segid);
        if(!(mapaddr=shmat(segid, 0, 0))) {
            trxdbg(0,1,0,"Could mmap shared memory segment\n");
        }
        else {
            /* get the size */
            struct shmid_ds stats;
            trxdbg(1,0,0,"Shared memory segment attached at 0x%08x\n", mapaddr);
            if(!shmctl(segid, IPC_STAT, &stats)) {
                int nentries=stats.shm_segsz/RPTSLOTSIZE;
                trxdbg(1,0,0,"Mapped segment size if %d - %d entries\n", stats.shm_segsz, nentries);
                switch(clients[idx].subCmd) {
                    case REPORT_REPORT:
                    {
                        void **vector;
                        if((vector=malloc(sizeof(void *)*nentries))) {
                            // fill the vector 
                            int i;
                            size_t total;
                            if(!summary) {
                                cliPrt(cliIdx, "===========================================================\n");
                                cliPrt(cliIdx, "Start of report for registered client '%s' pid %d\n", clients[idx].name,  clients[idx].pid);
                                cliPrt(cliIdx, "===========================================================\n");
                            }
                            for(i=0;i<nentries;i++) vector[i]=mapaddr+sizeof(int)+(i*RPTSLOTSIZE);
                            qsort(vector, nentries, sizeof *vector, cmpBackTraces);
                            buildShowTree(cliIdx, nentries, vector, &total);
                            if(!summary) cliPrt(cliIdx, "===========================================================\n");
                            cliPrt(cliIdx, "%-20s [pid %6d] [Proc Size : %6d] [Mallocated - total ->%6d - tagged -> %10d\n"
                                , clients[idx].name, clients[idx].pid, getClientVsize(idx), *((int*)mapaddr), total);
                            if(!summary) {
                                cliPrt(cliIdx, "===========================================================\n");
                                cliPrt(cliIdx, "End of report for registered client '%s' pid %d\n", clients[idx].name,  clients[idx].pid);
                                cliPrt(cliIdx, "===========================================================\n");
                            }
                        }
                        else trxdbg(0,0,0,"Out of memory on orderring vector allocation [%d bytes]\n", sizeof(uint32_t)*nentries);
                    }
                    break;
                    case REPORT_SNAP:{
                        // make copy of the current allocations 
                        if(clients[idx].snap) free(clients[idx].snap);
                        if((clients[idx].snap=malloc(stats.shm_segsz))) {
                            int i;
                            void *p=mapaddr;
                            memmove(clients[idx].snap, mapaddr, stats.shm_segsz);
                            clients[idx].snapsize=stats.shm_segsz;
                            // change the computed sizes to negative values
                            for(i=0, p=clients[idx].snap+sizeof(int); i<nentries; i++, p+=RPTSLOTSIZE) {
                                *(int*)p = -*(int*)p;
                            }

                        }
                        else cliPrt(cliIdx, "Could not allocate snap buffer of %d bytes\n", stats.shm_segsz);
                    }
                    break;
                    case REPORT_SREPORT:{
                        // show difference in allocation between current report and last snap command.
                        // the approach is to negate the snap sizes and treat the entries of bot the report
                        // and the snap as a single report...
                        if(clients[idx].snap) {
                            void **vector;
                            int nsnap=clients[idx].snapsize/RPTSLOTSIZE, j;
                            if((vector=malloc(sizeof(void *)*(nentries+nsnap)))) {
                                // fill the vector 
                                int i;
                                size_t total;
                                if(!summary) {
                                    cliPrt(cliIdx, "===========================================================\n");
                                    cliPrt(cliIdx, "Start of report for registered client '%s' pid %d\n", clients[idx].name,  clients[idx].pid);
                                    cliPrt(cliIdx, "===========================================================\n");
                                }
                                for(i=0;i<nentries;i++) vector[i]=mapaddr+sizeof(int)+(i*RPTSLOTSIZE);
                                for(j=0;j<nsnap;j++) vector[i+j]=clients[idx].snap+sizeof(int)+(j*RPTSLOTSIZE);
                                qsort(vector, nentries+nsnap, sizeof *vector, cmpBackTraces);
                                buildShowTree(cliIdx, nentries+nsnap, vector, &total);
                                if(!summary) cliPrt(cliIdx, "===========================================================\n");
                                cliPrt(cliIdx, "%-20s [pid %6d] [Proc Size : %6d] [Mallocated - total ->%6d - tagged -> %10d\n"
                                    , clients[idx].name, clients[idx].pid, getClientVsize(idx), *((int*)mapaddr), total);
                                if(!summary) {
                                    cliPrt(cliIdx, "===========================================================\n");
                                    cliPrt(cliIdx, "End of report for registered client '%s' pid %d\n", clients[idx].name,  clients[idx].pid);
                                    cliPrt(cliIdx, "===========================================================\n");
                                }
                            }
                            else trxdbg(0,0,0,"Out of memory on orderring vector allocation [%d bytes]\n", sizeof(uint32_t)*nentries);
                        }
                        else cliPrt(cliIdx, "Please execute a snap command first.\n", stats.shm_segsz);
                    }
                    break;
                }
            }
            shmdt(mapaddr);
        }
        shmctl(segid, IPC_RMID, 0);
    }    
    cliDecWait(cliIdx);
}

/* client to server exchanges */
static void handleExchange(int idx)
{
    trxdbg(1,0,0,"handleExchange with client idx %d fd %d\n", idx, clients[idx].fd);
    if(rcvCmd(clients[idx].fd, clientRcvCB, idx) < 0) {
        cliDecWait(clients[idx].reportTo);
        closeClient(idx);
     } else {
        if(clients[idx].needConfig) {

            sendConfig(idx);
            clients[idx].needConfig=0;
        }
        if(clients[idx].produceFinalReport) {

            clients[idx].produceFinalReport=0;
            showReport(idx);
        }   
    }
}

static int serverFd=(-1);

static void newClient()
{
int sock;

    if ((sock=accept(serverFd, 0, 0)) == -1)
        trxdbg(0,1,0, "New clent connection failed (accept)");
    else {
    
        /* create a new client entry */
        int idx;
        trxdbg(1,0,0,"sock is %d\n",sock);
        for(idx=0;idx<MAXCLIENTS;idx++) {
        
            if(clients[idx].fd<0) break;
            
        }
        if(idx==MAXCLIENTS) {
            trxdbg(0,0,0,"Ran out of client entries.... Dropping connection.\n");
            close(sock);
        }
        else {
            trxdbg(1,0,0,"New client on idx %d fd %d\n", idx, sock);
            clients[idx].fd=sock;
        }
    }
}

int clientSetFds(fd_set *fdset, int maxfd)
{
int idx;

    if(serverFd >= 0) {
        setfd(serverFd);
    }
    for(idx=0; idx<MAXCLIENTS; idx++) {

        if(clients[idx].fd>=0) {
            setfd(clients[idx].fd);
        }

    }
    return maxfd;
}

void clientProcessFds(fd_set *fdset)
{
int idx;

    if(serverFd >= 0 && FD_ISSET(serverFd, fdset)) {
        newClient();
    }
    for(idx=0; idx<MAXCLIENTS; idx++) {

        if(clients[idx].fd>=0 && FD_ISSET(clients[idx].fd, fdset)) {
            trxdbg(1,0,0,"Setting fd bit %d for idx %d\n", clients[idx].fd, idx);
            handleExchange(idx);
        }
    }
}

void setupClientSocket()
{
int s, len, i;
struct sockaddr_un addr;

    if ((s = socket(AF_UNIX, SOCK_STREAM, 0)) == -1)
        trxdbg(0,1,1, "socket");

    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, TPMDBG_SOCKPATH);
    unlink(addr.sun_path);
    len = strlen(addr.sun_path) + sizeof(addr.sun_family);
    if (bind(s, (struct sockaddr *)&addr, len) == -1) 
        trxdbg(0,1,1, "bind");

    if (listen(s, 5) == -1)
        trxdbg(0,1,1, "listen");
    
    serverFd=s;
    for(i=0;i<MAXCLIENTS;i++) clients[i].fd=-1;
}

void shutdownClientSocket()
{
    if(serverFd>=0) {
        close(serverFd);
        unlink(TPMDBG_SOCKPATH);
    }
}
