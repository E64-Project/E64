/* Execute the complete production FatFs implementation with an in-memory disk. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include FF_SOURCE
PARTITION VolToPart[FF_VOLUMES]={{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,0,0},{5,0,0},{6,0,0}};
static unsigned char *media;
static size_t media_size;
static LBA_t fail_sector=(LBA_t)-1;
static int fail_sync, partial_failure;
static unsigned writes,syncs,reads,failures;
static LBA_t write_log[8192];
DSTATUS disk_initialize(BYTE p){return p?STA_NOINIT:0;}
DSTATUS disk_status(BYTE p){return p?STA_NOINIT:0;}
DRESULT disk_read(BYTE p,BYTE*b,LBA_t s,UINT n){assert(!p&&n&&(size_t)s*512+(size_t)n*512<=media_size);reads++;memcpy(b,media+(size_t)s*512,(size_t)n*512);return RES_OK;}
DRESULT disk_write(BYTE p,const BYTE*b,LBA_t s,UINT n){assert(!p&&n&&(size_t)s*512+(size_t)n*512<=media_size);assert(writes<8192);write_log[writes++]=s;if(s<=fail_sector&&fail_sector<s+n){failures++;if(partial_failure)memcpy(media+(size_t)s*512,b,137);return RES_ERROR;}memcpy(media+(size_t)s*512,b,(size_t)n*512);return RES_OK;}
DRESULT disk_ioctl(BYTE p,BYTE cmd,void*b){assert(!p);if(cmd==CTRL_SYNC){syncs++;return fail_sync?RES_ERROR:RES_OK;}if(cmd==GET_SECTOR_COUNT){*(LBA_t*)b=media_size/512;return RES_OK;}if(cmd==GET_SECTOR_SIZE){*(WORD*)b=512;return RES_OK;}if(cmd==GET_BLOCK_SIZE){*(DWORD*)b=1;return RES_OK;}return RES_PARERR;}
DWORD get_fattime(void){return (DWORD)(46<<25|1<<21|1<<16);}
void*ff_memalloc(UINT n){return malloc(n);}void ff_memfree(void*p){free(p);}
int ff_mutex_create(int v){(void)v;return 1;}void ff_mutex_delete(int v){(void)v;}
int ff_mutex_take(int v){(void)v;return 1;}void ff_mutex_give(int v){(void)v;}
static void reset_fault(void){fail_sector=(LBA_t)-1;fail_sync=0;partial_failure=0;}
static void dirty_fat(FATFS*fs,BYTE expected[512]){assert(!fs->wflag);LBA_t s=fs->fatbase+fs->fsize-1;assert(move_window(fs,s)==FR_OK);fs->win[511]^=0x5a;memcpy(expected,fs->win,512);fs->wflag=1;}
int main(int argc,char**argv){assert(argc==4);FILE*f=fopen(argv[1],"rb");assert(f);assert(!fseek(f,0,SEEK_END));media_size=ftell(f);rewind(f);media=malloc(media_size);assert(media);assert(fread(media,1,media_size,f)==media_size);assert(!fclose(f));
 FATFS fs;assert(f_mount(&fs,"SD:",1)==FR_OK);assert(fs.fs_type==atoi(argv[2]));assert(fs.n_fats==2);const char*mode=argv[3];BYTE expected[512];
 if(!strcmp(mode,"primary")||!strcmp(mode,"secondary")||!strcmp(mode,"partial-secondary")){
  dirty_fat(&fs,expected);LBA_t primary=fs.winsect;fail_sector=primary+(!strcmp(mode,"primary")?0:fs.fsize);partial_failure=!strcmp(mode,"partial-secondary");unsigned before=writes;
  assert(sync_window(&fs)==FR_DISK_ERR);assert(fs.wflag==1&&fs.winsect==primary&&!memcmp(fs.win,expected,512));assert(writes-before==(!strcmp(mode,"primary")?1U:2U));assert(syncs==0);
  reset_fault();assert(sync_window(&fs)==FR_OK&&!fs.wflag);assert(!memcmp(media+(size_t)primary*512,expected,512));assert(!memcmp(media+(size_t)(primary+fs.fsize)*512,expected,512));
 }else if(!strcmp(mode,"fsinfo")){
  assert(fs.fs_type==FS_FAT32);fs.fsi_flag=1;fail_sector=fs.volbase+1;unsigned before=syncs;assert(sync_fs(&fs)==FR_DISK_ERR);assert(fs.fsi_flag==1&&syncs==before);reset_fault();assert(sync_fs(&fs)==FR_OK&&!fs.fsi_flag);assert(ld_32(media+(size_t)(fs.volbase+1)*512+FSI_Free_Count)==fs.free_clst);
 }else{
  FIL fp;UINT n;BYTE payload[900],back[900];for(unsigned i=0;i<sizeof payload;i++)payload[i]=(BYTE)(i*31);assert(f_open(&fp,"SD:/B1TEST.BIN",FA_CREATE_ALWAYS|FA_WRITE|FA_READ)==FR_OK);assert(f_write(&fp,payload,sizeof payload,&n)==FR_OK&&n==sizeof payload);
  if(!strcmp(mode,"sync")||!strcmp(mode,"close-sync"))fail_sync=1;
  else if(!strcmp(mode,"file-fsinfo")){assert(fs.fs_type==FS_FAT32);fs.fsi_flag=1;fail_sector=fs.volbase+1;}
  else if(!strcmp(mode,"directory"))fail_sector=fp.dir_sect;
  else if(!strcmp(mode,"file-primary")||!strcmp(mode,"file-secondary")){assert(sync_window(&fs)==FR_OK);dirty_fat(&fs,expected);fail_sector=fs.winsect+(!strcmp(mode,"file-primary")?0:fs.fsize);}
  if(strcmp(mode,"success")){
   assert(fp.flag&FA_MODIFIED);unsigned before=syncs;FRESULT r=!strcmp(mode,"close-sync")?f_close(&fp):f_sync(&fp);assert(r==FR_DISK_ERR);assert(fp.flag&FA_MODIFIED);assert(fp.obj.fs==&fs);
   if(fail_sector!=(LBA_t)-1)assert(syncs==before); /* Preserve first metadata error: no later CTRL_SYNC. */
   unsigned failed=failures;assert((!strcmp(mode,"close-sync")?f_close(&fp):f_sync(&fp))==FR_DISK_ERR);assert(fp.flag&FA_MODIFIED);assert(fail_sync||failures>failed);
  }
  reset_fault();unsigned before=syncs;assert(f_sync(&fp)==FR_OK);assert(!(fp.flag&FA_MODIFIED));assert(syncs>before);assert(f_close(&fp)==FR_OK);assert(f_open(&fp,"SD:/B1TEST.BIN",FA_READ)==FR_OK);assert(f_read(&fp,back,sizeof back,&n)==FR_OK&&n==sizeof back&&!memcmp(back,payload,n));assert(f_close(&fp)==FR_OK);
 }
 printf("PASS: production FatFs FAT%d %s writes=%u syncs=%u injected_failures=%u\n",fs.fs_type==FS_FAT16?16:32,mode,writes,syncs,failures);assert(f_mount(NULL,"SD:",0)==FR_OK);if(!strcmp(mode,"success")){unsigned long long hash=14695981039346656037ULL;for(size_t i=0;i<media_size;i++){hash^=media[i];hash*=1099511628211ULL;}printf("image_fnv64=%016llx\n",hash);}free(media);return 0;
}
