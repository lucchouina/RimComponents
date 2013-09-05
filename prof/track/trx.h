#ifndef __trx_h__
#define __trx_h__
#ifdef __linux__
#include <stdint.h>
#endif
#include <sys/types.h>
/* socket file used for communication between managed client and manager */
#define TPMDBG_SOCKPATH "/tmp/trxdbg.sock"

/* default configuration file path */
#define TPMDBG_CONFFILE "/etc/trxdbg.conf"
typedef unsigned long addr_t;
#define MAXCALLERS  10
#define RPTSLOTSIZE (sizeof(addr_t)*(MAXCALLERS)+(2*sizeof(uint32_t)))  // add 2 xtra words for size and type
#define RPTSLOTSIZE_FD (sizeof(addr_t)*(MAXOPENERS)+(2*sizeof(uint32_t)))  // add 2 xtra words for size and type
#define toEntry(i) ((uint32_t *)(base + (i*RPTSLOTSIZE)))
#define KEYBASE     12012
#define TAGCUR      100
#define ACK_TIMEOUT 1   // seconds to 
typedef enum {

    RESTYPE_MEMORY,
    RESTYPE_FILE,

} resType_t;

void closeCli(int idx);
int  cliNewCmd(char *cmd, int idx);
int  cliGetchar(int idx);
void cliPutStr(int idx, char *s);
void rl_shutdown(void *rl);
void *rl_init(int idx);
void rl_newChar(void *rl);

/* Port for CLI clients */
#define CLI_PORT    12012
/*
    Enum of possible command exchanged
*/
enum {

    // server -> client
    CMD_SET,        /* set a variable value */
    CMD_GET,        /* get a variable value */
    CMD_ENABLE,     /* arg: none */
    CMD_VALIDATE,   /* arg: bool on [0|1] */
    CMD_POISON,     /* arg: bool on [0|1] */
    CMD_TRACK,      /* arg: bool on [0|1] */
    CMD_TAG,        /* arg : <tag value> */
    CMD_REPORT,     /* arg : <tag value> */
    CMD_PUSH,       /* arg : <tag value> */
    CMD_POP,        /* arg : <tag value> */
    CMD_DONE,       /* done with command set */
    
    // client -> server
    CMD_REGISTER,   /* args : pid */
    
    // both . It's an [N]ACK
    CMD_ACK,        /* arg: return value of a GET if any */
    
};
#define TPCMD_MAGIC_STR "TpMd"


// variety of report commands
#define REPORT_REPORT   0
#define REPORT_SNAP     1
#define REPORT_SREPORT  2

/* struct of the command */
typedef struct cmd_s {

    char        magic[4];   // magic which is filled with *magic
    uint32_t    len;        // total len of the command including magic and len
    uint32_t    seq;        // sequencing
    char        cmd;
    uint32_t    aux[2];
} cmd_t;

/* Application config inside trxmgr */
typedef struct appdata_s {

    char cname[100];
    uint32_t flags;
    uint32_t tag;
    
} appdata_t;
#define MAXCNAME (sizeof(((appdata_t*)0)->cname))

#define FLAG_ENABLE         0x00000001
#define FLAG_POISON         0x00000002
#define FLAG_VALIDATE       0x00000004
#define FLAG_TRACK          0x00000008

typedef struct flgmap_s {

    const char *flgstr;
    int32_t mask;
    int cmd;
    
} flgmap_t;

extern flgmap_t flgmap[];
extern int NFLAGS;

/* shared functions */
void    trxdbg(int level, int doerr, int die, char *fmt, ...);
int     clientInit();
int     setupSig();
void    dbgsetlvl(int level);
int     dbggetlvl();
appdata_t *getAppConfig(char *name);
int     sendCmdMore(int fd, int seq, int cmd, int aux, int aux2, int more, char *pmore, int (*cb)(char **buf));
int     recvAck(int fd, uint32_t *seq);
void    sendMgr(int cmd, int aux, int aux2);
void    trxmgrClientWalkList(int idx, void (*cb)(int idx, int client, char *name));
int     trxmgrClientGetVar(int client, int cmd);
int     trxmgrClientSetVar(int client, int var, int value);
int     rcvCmd(int fd, int (*cb)(int idx, cmd_t *cmd, int more, char *pmore), int idx);
void    libSendReport(int fd, int tag);
int     clientsPid(int idx);
int     trxmgrClientAskReport(int client, int idx, int tag, int subcmd);
int     trxmgrClientAskPop(int client, int idx);
int     trxmgrClientAskPush(int client, int idx);
void    cliPrt(int idx, char *fmt, ...);
void    cliDecWait(int cidx);
void    rlShowPrompt(void *rl, int reset);
int     flagMask(char *flag);
void    buildShowTree(int cliIdx, int nentries, void **vector, size_t *total);
int     clientSetFds(fd_set *fdset, int maxfd);
void    clientProcessFds(fd_set *fdset);
void    setupClientSocket();
void    shutdownClientSocket();
void    setupCliSocket();
int     cliSetFds(fd_set *fdset, int maxfd);
void    cliProcessFds(fd_set *fdset);
void    setupCliSocket();
void    shutdownCliSocket();
#endif
