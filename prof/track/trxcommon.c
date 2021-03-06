#include <stdio.h>
#include <stdarg.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <syslog.h>
#include "trx.h"
static int dbglvl=0;

flgmap_t flgmap[] = {

    { "enable", FLAG_ENABLE, CMD_ENABLE},
    { "poison", FLAG_POISON, CMD_POISON},
    { "validate", FLAG_TRACK, CMD_TRACK},
    { "track", FLAG_VALIDATE, CMD_VALIDATE},
};
int NFLAGS=(sizeof(flgmap)/sizeof(flgmap[0]));
int flagMask(char *flag)
{
int i;

    for(i=0; i<NFLAGS; i++) {
        if(!strcasecmp(flgmap[i].flgstr, flag)) 
            return flgmap[i].mask;
    }
    return -1;
}

int syslogOn=0;

void trxdbg(int level, int doerr, int die, char *fmt, ...)
{
va_list ap;
int docr=0;
char myfmt[1024];
char msg[1024], *p=msg;
static int pid=-1;

    if(level>dbglvl) return;
    if(pid<0) pid=getpid();
    sprintf(myfmt, "[%d] ", pid);
    strcat(myfmt, fmt);
    // remove trailing CR
    if(myfmt[strlen(myfmt)-1]=='\n') {
        myfmt[strlen(myfmt)-1]='\0';
        docr=1;
    }
    va_start(ap, fmt);
    p += vsnprintf(p, 1024-(p-msg), myfmt, ap);
    if(doerr) {
        char errbuf[100];
        snprintf(errbuf, sizeof errbuf, "error [%d]", errno);
        p += snprintf(p, 1024-(p-msg), " : %s", errbuf);
    }
    if(docr || doerr) *p++='\n';
    *p='\0';
    if (syslogOn == 1) syslog(LOG_DEBUG, "%s", msg);
    else write(2, msg, p-msg);
    va_end(ap);
    if(die) exit(1);
}

void dbgsetlvl(int level)
{
    dbglvl=level;
}
int dbggetlvl()
{
    return dbglvl;
}

#define CMDLEN  sizeof(cmd_t)
int recvAck(int fd, uint32_t *seq)
{
cmd_t pkt;
int val=-1, n;
fd_set fdset;
struct timeval tv={ tv_sec: ACK_TIMEOUT };

    FD_ZERO(&fdset);
    FD_SET(fd, &fdset);
    if((n=select(fd+1, &fdset, 0, 0, &tv))>0) {

        trxdbg(1,0,0,"recvAck for seq %d\n", *seq);
        if(read(fd, &pkt, CMDLEN) != CMDLEN) {
            trxdbg(1,1,0,"Failed pkt read.\n", fd);
        }
        else {

            trxdbg(1,0,0,"Received [cmd=%d] pkt[%d]-[%d] with ack = %d\n", pkt.cmd, pkt.seq, *seq, pkt.aux[0]);
            if(pkt.cmd != CMD_ACK) {
                trxdbg(0,0,0,"Invalid command in ack [%d] -[%d]\n", pkt.cmd, CMD_ACK);
            }
            else {
                if(*seq != pkt.seq) {
                    trxdbg(0,0,0,"out of sequence on pkt receive [%d] -[%d]\n", pkt.seq, *seq);
                }
                else val=pkt.aux[0];
            }
        }
        *seq+=1;
    }
    else {
    
        if(!n) {
            trxdbg(1,1,0,"Timeout waiting for client socket %d", fd);
        }
        else {
        
            trxdbg(1,1,0,"Error select'ing from client socket %d", fd);
        }
    }
    return val;
}

int sendCmdMore(int fd, int seq, int cmd, int aux, int aux2, int more, char *pmore, int (*cb)(char **buf))
{
cmd_t pkt;
int pos=0;

    trxdbg(1,0,0,"Sending seq %d command %d to fd %d\n", seq, cmd, fd);
    trxdbg(1,0,0,"aux1 %d aux2 %d more %d pmore=0x%08x cb=0x%08x\n", aux, aux2, more, pmore, cb);
    strncpy(pkt.magic, TPCMD_MAGIC_STR, strlen(TPCMD_MAGIC_STR));
    pkt.len=CMDLEN+more;
    pkt.cmd=cmd;
    pkt.seq=seq;
    pkt.aux[0]=aux;
    pkt.aux[1]=aux2;
    if(write(fd, &pkt, CMDLEN)==CMDLEN) {
    
        if(pmore) {
            while(more) {

                int nw=write(fd, pmore+pos, more);

                if(nw<0) return 0;
                more -= nw;
                pos += nw;
            }
        }
        else if(more) { // use the callback to get more data
            char *buf;
            int nr;
            while((nr=(*cb)(&buf))) {
                int left=nr, pos=0;
                while(left) {
                
                    int nw;
                    if((nw=write(fd, buf+pos, left)) < 0) return 0;
                    left-=nw;
                    pos+=nw;
                }
            }
        }
        return 1;
    }
    else trxdbg(1,0,0,"Short right on sendcmd?!\n");
    return 0;
}

void sendAck(int fd, cmd_t *cmd, int val)
{
    sendCmdMore(fd, cmd->seq, CMD_ACK, val, 0, 0, 0, 0);
}

int rcvCmd(int fd, int (*cb)(int idx, cmd_t *cmd, int more, char *pmore), int idx)
{
cmd_t pkt;

    trxdbg(1,0,0,"rcvCmd on fd %d idx %d\n", fd, idx);
    if(read(fd, &pkt, CMDLEN) != CMDLEN) {
        trxdbg(1,1,0,"Failed pkt read fd=%d.\n", fd);
    }
    else {
    
        trxdbg(1,0,0,"rcvCmd got one!\n");
        /* some validation */
        if(strncmp(pkt.magic, TPCMD_MAGIC_STR, sizeof pkt.magic)) {
        
            trxdbg(0,0,0,"Invalid MAGIC on command [seq:%d]\n", pkt.seq);
        }
        else {
        
            int more,left,ackval;
            left=more=pkt.len-CMDLEN;
            /* process any xtra data in the command */
            char *pmore=0;
            trxdbg(1,0,0,"rcvCmd left=%d\n", left);
            if(left) {
                if((pmore=malloc(left))) { // XXX This is from the serve size only at this time. 
                                           // So calling malloc is fine. should call realMalloc  if client
                    int nr=1, pos=0;
                    while(left && (nr=read(fd, pmore+pos, left))>0) {
                        left-=nr;
                        pos+=nr;
                    }
                    if(nr<=0) {

                        trxdbg(0,1,0,"Error on xtra payload read.\n");
                        free(pmore);
                        return -1;
                    }
                }
                else {
                    trxdbg(0,0,0,"Out of memory on xtra payload buffer allocation for %d bytes\n", left);
                    /* do our best to read and drop the rest of the command */
                    int nr=1, pos=0;
                    while(left && (nr=read(fd, pmore+pos, left))>0) {
                        left-=nr;
                        pos+=nr;
                    }
                    return -1;
                }
            }
            /* we've got everything */
            /* callee gets to free the pmore allocation */
            ackval=(*cb)(idx, &pkt, more, pmore);
            
            /* send a [N]ACK to sender */
            sendAck(fd, &pkt, ackval);
            if(pmore) free(pmore);
            trxdbg(1,0,0,"rcvCmd done and sent ackval %d!\n", ackval);
            return ackval;
        }
    }
    trxdbg(1,0,0,"rcvCmd done and error occurred!\n");
    return -1;
}
