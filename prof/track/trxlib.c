/*

    This file contains a simple set of library overloads that will
    work with the TP memory tracking framework to supply information
    on how much memory is allocated and where as well as execite
    configuration commands from the framework or user.
    
     #include <stdlib.h>

     void *malloc(size_t size);

     void *calloc(size_t nelem, size_t elsize);

     void free(void *ptr);

     void *memalign(size_t alignment, size_t size);

     void *realloc(void *ptr, size_t size);

     void *valloc(size_t size);

     #include <alloca.h>

     void *alloca(size_t size);
*/
#include <stdlib.h>
#include <sys/types.h>
#include <stdio.h>
#include <unistd.h>
#include <strings.h>
#include <string.h>
#include <pthread.h>
#include <fcntl.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <errno.h>
#include <stdarg.h>
#include <syslog.h>

#define __USE_GNU
#include <dlfcn.h>

#include "trx.h"
#include "trxlist.h"

/* some of the config variables we use */
extern uint32_t enable, tracking, validate, poison, alloctag;
static uint32_t pagesize, curalloc=0, initted=0, ininit=0;

/* lock for mp support */
static pthread_mutex_t trxm=PTHREAD_MUTEX_INITIALIZER;
#define LOCK    (pthread_mutex_lock(&trxm))
#define UNLOCK  (pthread_mutex_unlock(&trxm))

typedef void *type_malloc(size_t size);
typedef void *type_calloc(size_t nelem, size_t elsize);
typedef void  type_free(void *ptr);
typedef void *type_memalign(size_t alignment, size_t size);
typedef void *type_realloc(void *ptr, size_t size);
typedef void *type_valloc(size_t size);

/* file descriptors type of calls  for fd tracking */
typedef int type_dup(int oldfd);
typedef int type_dup2(int oldfd, int newfd);
typedef int type_open(const char *pathname, int flags, mode_t mode);
typedef int type_openat(int dirfd, const char *pathname, int flags, ...);
typedef int type_creat(const char *pathname, mode_t mode);
typedef int type_close(int fd);
typedef int type_pipe(int filedes[2]);
typedef int type_socket(int domain, int type, int protocol);
typedef int type_accept(int sockfd, void *addr, void *addrlen);

typedef int type_fork(void);

#define MAGIC1 0x1badc0de
#define MAGIC2 0xc0defee0
#define mkbusy(m) (m|=1)
#define mkfree(m) (m&=~1)
#define isbusy(m) (m|1)

#define MAXFREERS  4

#define MINALLOC    int32_t
#define trxAlign(s) ((s+sizeof(MINALLOC)-1)&~(sizeof(MINALLOC)-1))
#define OFFSET_OFFSET   0
#define OFFSET_SIZE     1
#define OFFSET_MAGIC    2
#define OFFSET_NWORDS   3 // used in buffer alignment

// how to dump core
#define COREDUMP *(int*)0=0
typedef struct trxblk_s trxblk_t;
#define MAXTAGS 255
typedef struct {
    int total;
    LIST_HEAD(xxx, trxblk_s) list;
} alist_t;

static alist_t alist[MAXTAGS];

struct trxblk_s {

    LIST_ENTRY(trxblk_s) list;		// active list linkage
    uint32_t    tag;                    // current tag number
    addr_t    callers[MAXCALLERS];
    addr_t    freers[MAXFREERS];
    /* following 3 fields need to be in that order to match the indexing used
       when tracking is !enable (see #defined above) */
    size_t      offset;     /* offset to the start of the start of the allocated buffer */
    size_t      size;       /* original size of the request for realloc() */
    uint32_t    magic;
};

struct {

    type_malloc     *realMalloc;
    type_realloc    *realRealloc;
    type_calloc     *realCalloc;
    type_free       *realFree;
    type_memalign   *realMemalign;
    type_valloc     *realValloc;
    
    type_dup        *realDup;
    type_dup2       *realDup2;
    type_open       *realOpen;
    type_openat     *realOpenat;
    type_creat      *realCreat;
    type_close      *realClose;
    type_pipe       *realPipe;
    type_socket     *realSocket;
    type_accept     *realAccept;
    
    type_fork       *realFork;

} realFuncs;

static int countFds(int tag);
static void addFds(void *, int sizeslot, int curpos, int maxpos, int tag);

/* Function called from the client code trxclient.c to send a full report to
   the manager. So as to not have the client app hang in signal handler for too long, we only do 
   part of the job here i.e. put all of te traces into a shared memory segment with an additional 
   word at the start of each traces for linkage and size */
void libSendReport(int cliIdx, int tag)
{
trxblk_t *tp;
uint32_t total=0;
size_t segsize;
int segid;
int shm_open(const char *name, int oflag, mode_t mode);

    trxdbg(1,0,0,"libSendReport : cliIdx %d tag %d\n", cliIdx, tag);
    // grab the lock
    LOCK;
    /* first pass - how many entries at that tag level */
    LIST_FOREACH(tp, &alist[tag].list, list) {
        total++;
    }
    trxdbg(1,0,0,"libSendReport : found %d entries\n", total);
    total += countFds(tag);
    
    if(total) {
    
        /* create a shared memory segment tp contain this data 
           We have 4 additional field to leave space for btree linkage
        */
        segsize=total*RPTSLOTSIZE;
        segsize += sizeof(int);
        trxdbg(1,0,0,"Seg size for report is %u\n", segsize);
        if((segid=shmget(KEYBASE+getpid(), segsize, IPC_CREAT+0666)) < 0)
            trxdbg(0,1,0,"Could not open shared memory segment.\n");
        else {
            void *pslot, *mapaddr;
            trxdbg(1,0,0,"Attaching to segment ID %d\n", segid);
            if((pslot=mapaddr=shmat(segid, 0, 0))==(void*)-1) {
                trxdbg(0,1,0,"Could not attach to shared memory segment [ size=%d pslot=0x%08x  errno : %d].\n"
                        , segsize, segid, errno);
                shmctl(segid, IPC_RMID, 0);
            }
            else {
                int newtot=0;
                trxdbg(1,0,0,"Mapped segment to 0x%08x\n", pslot);
                ((int*)pslot)[0]=curalloc;
                pslot += sizeof(int);
                /* transfer info */
                LIST_FOREACH(tp, &alist[tag].list, list) {
                    if(newtot>total) break;
                    newtot++;
                    memmove(pslot+8,  tp->callers, MAXCALLERS*sizeof(addr_t));
                    ((int*)pslot)[0]=tp->size;
                    ((int*)pslot)[1]=RESTYPE_MEMORY;
                    pslot += RPTSLOTSIZE;

                    #ifdef DEBUG                 
                    {
                    int i, *p=(int*)(pslot-RPTSLOTSIZE);
                       trxdbg(2,0,0,"One slot:");
                        for(i=0;i<MAXCALLERS+1;i++){

                            trxdbg(2,0,0,"[0x%08x]", p[i]);

                        }
                        trxdbg(2,0,0,"\n");
                    }
                    #endif                 
                }
                UNLOCK;
                /* add the fd traces */
                addFds(pslot, RPTSLOTSIZE, newtot, total, tag);
                shmdt(mapaddr);
                sendMgr(CMD_REPORT, 1, curalloc);
                return;
            }
            shmctl(segid, IPC_RMID, 0);
        }
    }
    sendMgr(CMD_REPORT, 0, curalloc);
    UNLOCK;
}

/* make the dyn lynker call trxdbginit() right after the load */
static void _init(void)
{
char *dbgvalstr;
int dbgval;
int missing=0;
extern int syslogOn;

    if(initted) {
        return;
    }
    ininit=1;
    trxdbg(1,0,0,"TPMDBG enabled !\n");
    openlog("trxclient", LOG_PID, LOG_USER);
    syslogOn=1;
    /*
        Make a list fo the real symbols.
        fatal is any of the symbols are not resolved.
    */
    if((dbgvalstr=getenv("TPMDEBUG"))) {
        if((dbgval=atoi(dbgvalstr))>=0) dbgsetlvl(dbgval);
        else trxdbg(0,0,0,"Invalid debug level value past in environment [%s]\n", dbgvalstr);
    }
    
    trxdbg(1,0,0,"trxdbginit : start\n");

    if(!(
        (realFuncs.realMalloc    = (type_malloc*)    dlsym(RTLD_NEXT, "malloc"))
        && ++missing &&
        (realFuncs.realCalloc    = (type_calloc*)    dlsym(RTLD_NEXT, "calloc"))
        && ++missing &&
        (realFuncs.realRealloc   = (type_realloc*)   dlsym(RTLD_NEXT, "realloc"))
        && ++missing &&
        (realFuncs.realFree      = (type_free*)      dlsym(RTLD_NEXT, "free"))
        && ++missing &&
        (realFuncs.realMemalign  = (type_memalign*)  dlsym(RTLD_NEXT, "memalign"))
        && ++missing &&
        (realFuncs.realValloc    = (type_valloc*)    dlsym(RTLD_NEXT, "valloc"))
        && ++missing &&
        (realFuncs.realDup       = (type_dup*)       dlsym(RTLD_NEXT, "dup"))
        && ++missing &&
        (realFuncs.realDup2      = (type_dup2*)      dlsym(RTLD_NEXT, "dup2"))
        && ++missing &&
        (realFuncs.realOpen      = (type_open*)      dlsym(RTLD_NEXT, "open"))
        && ++missing &&
#if 0
        (realFuncs.realOpenat    = (type_openat*)    dlsym(RTLD_NEXT, "openat"))
        && ++missing &&
#endif
        (realFuncs.realCreat     = (type_creat*)     dlsym(RTLD_NEXT, "creat"))
        && ++missing &&
        (realFuncs.realClose     = (type_close*)     dlsym(RTLD_NEXT, "close"))
        && ++missing &&
        (realFuncs.realPipe      = (type_pipe*)      dlsym(RTLD_NEXT, "pipe"))
        && ++missing &&
        (realFuncs.realSocket    = (type_socket*)    dlsym(RTLD_NEXT, "socket"))
        && ++missing &&
        (realFuncs.realAccept    = (type_accept*)    dlsym(RTLD_NEXT, "accept"))
        && ++missing &&
        (realFuncs.realFork      = (type_fork*)    dlsym(RTLD_NEXT, "fork"))

    )) trxdbg(0,0,1,"Could not resolve some of the overloaded functions missing=%d!\n", missing);
    
    trxdbg(1,0,0,"realMalloc=0x%08x\n", realFuncs.realMalloc);
    trxdbg(1,0,0,"realCalloc=0x%08x\n", realFuncs.realCalloc);
    trxdbg(1,0,0,"realRealloc=0x%08x\n", realFuncs.realRealloc);
    trxdbg(1,0,0,"realFree=0x%08x\n", realFuncs.realFree);
    trxdbg(1,0,0,"realMemalign=0x%08x\n", realFuncs.realMemalign);
    trxdbg(1,0,0,"realValloc=0x%08x\n", realFuncs.realValloc);
    trxdbg(1,0,0,"realDup=0x%08x\n", realFuncs.realDup);
    trxdbg(1,0,0,"realOpen=0x%08x\n", realFuncs.realOpen);
    trxdbg(1,0,0,"realCreat=0x%08x\n", realFuncs.realCreat);
    trxdbg(1,0,0,"realClose=0x%08x\n", realFuncs.realClose);
    trxdbg(1,0,0,"realPipe=0x%08x\n", realFuncs.realPipe);
    trxdbg(1,0,0,"realSocket=0x%08x\n", realFuncs.realSocket);
    trxdbg(1,0,0,"realAccept=0x%08x\n", realFuncs.realAccept);
    trxdbg(1,0,0,"realFork=0x%08x\n", realFuncs.realFork);

    // need this for handling valloc()
    pagesize=sysconf(_SC_PAGESIZE);
    trxdbg(1,0,0,"trxdbginit : page size is %d\n", pagesize);
    /*
        Open the connection to the management socket.
        If the manager is not listeing - forget it.
        So - not fatal, continue with '!enable'.
    */
    trxdbg(1,0,0,"trxdbginit : client setup.\n", pagesize);
    if(!clientInit()) enable=0;
    
    // Initialize the lists
    {
        int i;
        for(i=0;i<MAXTAGS;i++)
            LIST_INIT(&alist[i].list);
    }
    trxdbg(1,0,0,"trxdbginit : done enable=%d tracking=%d\n", enable, tracking);
    initted++;
    ininit=0;
    
}

#if defined(__i386)
#define PCPOS       1
#define FRAMEPOS    0
#define JUMPOVER    1  // number of frame to jump over before starting to record a backtrace
#elif defined(__sparc)
#define PCPOS       15
#define FRAMEPOS    14
#define JUMPOVER    1  // number of frame to jump over before starting to record a backtrace
#elif defined(__x86_64)
#define PCPOS       1
#define FRAMEPOS    0
#define JUMPOVER    1  // number of frame to jump over before starting to record a backtrace
#else
#error Currently supports only sparc and i386 processor abi
#endif
/* get a traceback */
static int tp_gettrace(addr_t *pc, int max)
{
#ifdef __GNUC__
    addr_t frame=(addr_t)__builtin_frame_address(0);
    addr_t base=frame;
#else
#error This file needs to be compiled with the GNU compiler (re: uses GNU __builtin...)
#endif
    int i1=0, i=0, n;

    trxdbg(1,0,0,"-\n");
    // jump over JUMPOVER frames to get to the actual callers
    while(
        i1<JUMPOVER 
        && frame 
        && frame > 0x1000000
        && (frame - base) < (16*1024*1024)
        && *(addr_t*)(frame+(PCPOS*sizeof(addr_t)))) {
        pc[i1]=*(addr_t*)(frame+(PCPOS*sizeof(addr_t)));
        trxdbg(1,0,0,"pc1[%d] 0x%p at 0x%p next is 0x%p\n"
            , i1
            , *(addr_t*)(frame+(PCPOS*sizeof(addr_t)))
            , (addr_t*)(frame+(PCPOS*sizeof(addr_t)))
            , *(addr_t*)(frame+(FRAMEPOS*sizeof(addr_t)))
            );
        frame=*(addr_t*)(frame+(FRAMEPOS*sizeof(addr_t)));
#if defined(__sparc)
        if(frame==0xffffffff) break;
#endif
        i1++;
    }
    if(i1<JUMPOVER) return 0;
    
    i=0;
    while(
        i<max 
        && frame 
        && frame > 0x1000000
        && (frame - base) < (16*1024*1024)
        && *(addr_t*)(frame+(PCPOS*sizeof(addr_t)))) {
        trxdbg(1,0,0,"pc2[%d] 0x%p at 0x%p next is 0x%p\n"
            , i1
            , *(addr_t*)(frame+(PCPOS*sizeof(addr_t)))
            , (addr_t*)(frame+(PCPOS*sizeof(addr_t)))
            , *(addr_t*)(frame+(FRAMEPOS*sizeof(addr_t)))
            );
        pc[i]=*(addr_t*)(frame+(PCPOS*sizeof(addr_t)));
        frame=*(addr_t*)(frame+(FRAMEPOS*sizeof(addr_t)));
        i++;
#if defined(__sparc)
        if(frame==0xffffffff) break;
#endif
    }
    // zap the rest of them
    n=i;
    while(i<max) pc[i++]=0;
    return n;
}

static __inline__ uint32_t chkblock(void *ptr)
{
    uint32_t*p=((uint32_t *)ptr)-3;
    if((p[OFFSET_MAGIC]!=MAGIC1)  && (p[OFFSET_MAGIC]!=MAGIC2)) {
        trxdbg(0,0,0,"Invalid block error [0x%08x] - aborting!\n", p[OFFSET_MAGIC]);
        COREDUMP;
    }
    return p[OFFSET_MAGIC];
}

static __inline__  void chkinit()
{
    if(!initted && !ininit) {
        _init();
    }
}

/*
    Core allocation function.
    
    - trim up the size to the nearest int32_t
    - check if we've been turned on.
*/
static void *tp_alloc(size_t size, int zero, uint32_t alignment)
{
    trxblk_t *tp;
    size_t tpsize;
    uint32_t overhead;
    char *p;
    static char earlybuf[10000];
    static int epos=0;
    
    trxdbg(1,0,0,"tp_alloc: size=%d\n", size);
    size=trxAlign(size);
    if(tracking) overhead=sizeof *tp+sizeof MAGIC1;
    else overhead=(OFFSET_NWORDS+1) * sizeof(uint32_t);
    
    // compute the final size and the offset based on alignment need
    // if alignment is specified we need to allocate three times the alignement more
    // then the asked size. Assuming the worst case where size is a multiple of 
    // the alignment and given the fact that we have a header and footer to
    // install. If the alignment is less then the needed overhead we compute 
    // the next alignment up (power of two) that is greater then the overhead.
    if(!alignment) alignment=sizeof(MINALLOC);
    tpsize=((alignment+overhead)<<1) + size;
    trxdbg(1,0,0,"Tpsize=%d realFunc.realMalloc=0x%08x tracking=%d\n", tpsize, realFuncs.realMalloc, tracking); 
    /* some of the dl implementation will try to malloc/calloc on first call.
       Need to support this initial allocation buffer because of that */
    if(!initted) {
        if((sizeof earlybuf - epos) >= tpsize) {
            int pos=epos;
            epos+=tpsize;
            return earlybuf+pos;
        }
    }
    else if((p=realFuncs.realMalloc(tpsize))) {
    
        // figure out where to put tp and our offset
        char *ph=(char*)(((addr_t)p+overhead+alignment)&(~(alignment-1)));
        
        if(tracking) {
        
            tp=((typeof(tp))ph)-1;
            // get the back track
            tp_gettrace(tp->callers, MAXCALLERS);
            tp->size=size;
            tp->magic=MAGIC2;
            tp->offset=ph-p;
            tp->tag=alloctag;
            if(zero) bzero(tp+1, size);
            *(int*)(ph+size)=MAGIC1;
            
            /* add this block to the allocation list */
            trxdbg(1,0,0,"Tracking one more - locking.\n");
            LOCK;
            trxdbg(1,0,0,"done.\n");
            LIST_INSERT_HEAD(&alist[tp->tag].list, tp, list);
            alist[tp->tag].total += size;
            curalloc += size;
            trxdbg(1,0,0,"Tracking return 0x%p curalloc=%d, tag=%d\n", tp+1, curalloc, tp->tag);
            UNLOCK;
            return tp+1;
        }
        else {
        
            uint32_t *pw=(uint32_t *)ph-OFFSET_NWORDS;
            pw[OFFSET_MAGIC]=MAGIC1;  // header
            pw[OFFSET_SIZE]=size;
            pw[OFFSET_OFFSET]=ph-(char*)p;
            if(zero) bzero(p+1, size);
            *(int*)(ph+size)=MAGIC1;
            curalloc += size;
            trxdbg(1,0,0,"Tagged return 0x%p curalloc=%d\n", ph, curalloc);
            return ph;
        }
    }
    return 0;
    
}

void *malloc(size_t size)
{
    chkinit();
    if(!enable) return realFuncs.realMalloc(size);
    else
        return tp_alloc(size, 0, 0);
}

void *calloc(size_t nelem, size_t elsize)
{
    chkinit();
    if(!enable && !ininit) return realFuncs.realCalloc(nelem, elsize);
    else 
        return tp_alloc(nelem*elsize, 1, 0);
}

static void verify(void* ptr)
{

    uint32_t *pw=((uint32_t*)ptr)-OFFSET_NWORDS;
    trxdbg(1,0,0,"Verify 0x%p\n", ptr);
    if(pw[OFFSET_MAGIC] != MAGIC1 && pw[OFFSET_MAGIC] != MAGIC2) {

        if(pw[OFFSET_MAGIC]==(MAGIC1+1) || pw[OFFSET_MAGIC]==(MAGIC2+1))
            trxdbg(0,0,0,"Double free on pointer 0x%p!\n", ptr);
        else
            trxdbg(0,0,0,"Invalid pointer 0x%p in free!\n", ptr);
        COREDUMP;
    }
    /* check the trailer */
    if(validate) {

        if(*((uint32_t*)(ptr+pw[OFFSET_SIZE])) != MAGIC1) {

            trxdbg(0,0,0,"Buffer overflow defected! Aborting...\n");
            COREDUMP;
        }
    }
}            

void free(void *ptr)
{
    chkinit();
    if(!enable) realFuncs.realFree(ptr);
    else {
        if(!ptr) return; // api should not fail on NULL pointer
        else {
        
            uint32_t *pw=((uint32_t*)ptr)-OFFSET_NWORDS;
            addr_t *ppc;
            uint32_t nppc=0;
            
            verify(ptr);
            
            /* remove from list if tracking */
            if(pw[OFFSET_MAGIC] == MAGIC2) {
                
                trxblk_t *tp=((trxblk_t*)ptr)-1;
                LOCK;
                if(validate) {
                    if(LIST_NEXT(tp,list)) verify(LIST_NEXT(tp,list)+1);
                    if((void*)LIST_PREV(tp,list) != (void*)&alist[tp->tag].list) verify(LIST_PREV(tp,list)+1);
                }
                alist[tp->tag].total -= pw[OFFSET_SIZE];
                curalloc -= pw[OFFSET_SIZE];
                LIST_REMOVE(tp,list);
                UNLOCK;
                nppc=tp_gettrace(tp->freers, MAXFREERS)*sizeof(addr_t);
                ppc=tp->freers;
            }
            else curalloc -= pw[OFFSET_SIZE];
            pw[OFFSET_MAGIC] |= 1;
            if(poison) {
            
                addr_t pad=-1;
                void *pp=ptr, *pend=ptr+pw[OFFSET_SIZE];
            
                if(!nppc) {
                    nppc=sizeof(addr_t);
                    ppc=&pad;
                }
                while(pp<pend) {
                    if(pend-pp < nppc) nppc=pend-pp;
                    memcpy(pp, ppc, nppc);
                    pp+=nppc;
                }
            
            }
            /* to the actual free */
            realFuncs.realFree(ptr-pw[OFFSET_OFFSET]);
        }
    }
}

/*
    for realloc, we always realloc.
    Meanning we reallocate to the new size and copy the content
    into the new buffer. This is why we record the original size
    in the header in the first place.
    
*/
void *realloc(void *ptr, size_t size)
{
    chkinit();
    if(!enable) return realFuncs.realRealloc(ptr, size);
    else {
        if(!ptr) return tp_alloc(size, 0, 0);
        else if(!size) free(ptr);
        else {
            void *new;
            uint32_t *pw=((uint32_t*)ptr)-OFFSET_NWORDS;
            verify(ptr);
            if((new=tp_alloc(size, 0, 0))) {

                size_t oldsize=pw[OFFSET_SIZE];
                size_t ncopy=oldsize>size?size:oldsize;
                memmove(new, ptr, ncopy);
                free(ptr);
            }
            return new;
        }
    }
    return 0;
}

void *memalign(size_t alignment, size_t size)
{
    chkinit();
    if(!enable) return realFuncs.realMemalign(alignment, size);
    if(alignment < sizeof(int)) return 0;
    return tp_alloc(size, 0, alignment);
}

void *valloc(size_t size)
{
    chkinit();
    if(!enable) return realFuncs.realValloc(size);
    return memalign(pagesize, size);
}

/* file descriptors handlers */
#define MAXFDS      1024
#define MAXOPENERS  6
#define MAXCLOSERS  4
typedef struct fd_s {

    addr_t    opener[MAXOPENERS];
    addr_t    closer[MAXCLOSERS];
    uint32_t    tag;
    int         inUse;
    
} fd_t;

static fd_t fds[MAXFDS];

static int countFds(int tag)
{
int i, tot=0;

    for(i=0;i<MAXFDS;i++) if(fds[i].inUse && fds[i].tag==tag) tot++;
    return tot;
}

static void addFds(void *pslot, int sizeslot, int curpos, int maxpos, int tag)
{
int i;
int max=sizeslot<RPTSLOTSIZE_FD?sizeslot:RPTSLOTSIZE_FD;

    for(i=0;i<MAXFDS && curpos<maxpos;i++) {
        if(fds[i].inUse && fds[i].tag==tag) {
            memmove(pslot+8,  fds[i].opener, max-8);
            ((int*)pslot)[0]=1;
            ((int*)pslot)[1]=RESTYPE_FILE;
            pslot += sizeslot;
            curpos++;
        }
    }
}

static int __inline__ fdIsValid(int fd)
{
    if(fd>=0 && fd<MAXFDS) return 1;
    else return 0;
}

static void newFd(int fd)
{
    if(!enable) return;
    if(fdIsValid(fd)) {
        tp_gettrace(fds[fd].opener, MAXOPENERS);
        if(!fds[fd].inUse) {
            fds[fd].inUse=1;     
            fds[fd].tag=alloctag;  
        }
        else trxdbg(1,0,0,"We lost track of allocation of fd %d! [0x%p] [0x%p]\n"
            , fd, fds[fd].opener[0], fds[fd].opener[1]);
    }
}

static int closeFd(int fd)
{
int ret;

    chkinit();
    ret=realFuncs.realClose(fd);
    if(!enable) return ret;
    if(!ret && fdIsValid(fd)) {
        
        tp_gettrace(fds[fd].closer, MAXCLOSERS);
        if(fds[fd].inUse) {
            fds[fd].inUse=0;
        }
        else trxdbg(1,0,0,"We lost track of allocation of fd %d! [0x%08x] [0x%08x]\n"
            , fd, fds[fd].closer[0], fds[fd].closer[1]);
    }
    return ret;
}

int dup(int oldfd)
{
    chkinit();
    return realFuncs.realDup(oldfd);
}

int dup2(int oldfd, int newfd)
{
    chkinit();
    return realFuncs.realDup2(oldfd, newfd);
}

int open(const char *pathname, int flags, ...)
{
va_list ap;
int fd;

    chkinit();
    va_start(ap, flags);
    fd=realFuncs.realOpen(pathname, flags, va_arg(ap, int));
    va_end(ap);
    newFd(fd);

    return fd;
}
#if 0
int openat(int dirfd, const char *pathname, int flags, ...)
{
va_list ap;
int fd;

    chkinit();
    va_start(ap, flags);
    fd=realFuncs.realOpenat(dirfd, pathname, flags, va_arg(ap, int));
    va_end(ap);
    newFd(fd);
    return fd;
}
#endif
int creat(const char *pathname, mode_t mode)
{
int fd;

    chkinit();
    fd=realFuncs.realCreat(pathname, mode);
    newFd(fd);
    return fd;
}

int close(int fd)
{
    return closeFd(fd);
}

int pipe(int *filedes)
{
int ret;

    chkinit();
    ret=realFuncs.realPipe(filedes);
    if(!ret) {
        newFd(filedes[0]);
        newFd(filedes[1]);
    }
    return ret;
}

int socket(int domain, int type, int protocol)
{
int fd;

    chkinit();
    fd=realFuncs.realSocket(domain, type, protocol);
    newFd(fd);
    return fd;
}

int accept(int sockfd, void *addr, void *addrlen)
{
int fd;

    chkinit();
    fd=realFuncs.realAccept(sockfd, addr, addrlen);
    newFd(fd);
    return fd;
}

pid_t fork(void)
{
int pid;

    chkinit();
    if((pid=realFuncs.realFork()) == 0) {
    
        /* if that worked, then lets close and re-register with mgr */
        if(enable) clientInit();
    }
    return pid;
}
