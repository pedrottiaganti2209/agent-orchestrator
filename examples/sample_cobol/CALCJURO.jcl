//CALCJURO JOB (ACCT001),'CALCULO JUROS',
//         CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1),
//         NOTIFY=&SYSUID,REGION=0M
//*
//* ================================================================ *
//* JCL PARA EXECUCAO DO PROGRAMA CALCJURO                          *
//* Calculo de juros compostos - modulo financeiro                   *
//* ================================================================ *
//*
//JOBLIB   DD DSN=SYS1.LOADLIB,DISP=SHR
//         DD DSN=PROD.MIGRATION.LOADLIB,DISP=SHR
//*
//STEP010  EXEC PGM=CALCJURO,REGION=512M
//STEPLIB  DD DSN=PROD.MIGRATION.LOADLIB,DISP=SHR
//*
//* Dataset de entrada com parametros do calculo
//INPUT    DD DSN=PROD.CALCJURO.INPUT(0),
//            DISP=SHR,
//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=27920)
//*
//* Dataset de saida com resultados
//OUTPUT   DD DSN=PROD.CALCJURO.OUTPUT(+1),
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(5,2),RLSE),
//            DCB=(RECFM=FB,LRECL=200,BLKSIZE=27800)
//*
//* Log de erros e auditoria
//ERRLOG   DD DSN=PROD.CALCJURO.ERRLOG,
//            DISP=SHR
//*
//SYSOUT   DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSUDUMP DD SYSOUT=*
//*
//*
//STEP020  EXEC PGM=SORT,COND=(0,NE,STEP010)
//* Ordena output por data de vencimento
//SORTIN   DD DSN=PROD.CALCJURO.OUTPUT(0),DISP=SHR
//SORTOUT  DD DSN=PROD.CALCJURO.SORTED(+1),
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(5,2),RLSE)
//SYSIN    DD *
  SORT FIELDS=(141,8,CH,A)
  RECORD TYPE=F,LENGTH=200
/*
//SYSOUT   DD SYSOUT=*
//*
