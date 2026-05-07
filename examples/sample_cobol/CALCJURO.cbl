      *================================================================*
      * CALCJURO - CÁLCULO DE JUROS COMPOSTOS                         *
      * Calcula o montante final com juros compostos                   *
      * Input: PRINCIPAL, TAXA-ANUAL, PRAZO-MESES                      *
      * Output: MONTANTE-FINAL, JUROS-TOTAL, PARCELA-MENSAL            *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALCJURO.
       AUTHOR. MIGRATION-TEAM.
       DATE-WRITTEN. 2024-01-01.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-Z16.
       OBJECT-COMPUTER. IBM-Z16.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
      *----------------------------------------------------------------*
      * Constantes e controle interno                                  *
      *----------------------------------------------------------------*
       01 WS-CONSTANTES.
          05 WS-MESES-ANO        PIC 9(02) VALUE 12.
          05 WS-ZERO             PIC 9(15)V9(06) COMP-3 VALUE 0.
          05 WS-UM               PIC 9(15)V9(06) COMP-3 VALUE 1.

       01 WS-VARIAVEIS.
          05 WS-TAXA-MENSAL      PIC 9(05)V9(08) COMP-3.
          05 WS-FATOR-ACUM       PIC 9(10)V9(10) COMP-3.
          05 WS-FATOR-TEMP       PIC 9(10)V9(10) COMP-3.
          05 WS-CONT-MESES       PIC 9(03) COMP.
          05 WS-DATA-VENCIMENTO  PIC 9(08).
          05 WS-ANO-BASE         PIC 9(04).
          05 WS-MES-BASE         PIC 9(02).
          05 WS-DIA-BASE         PIC 9(02).
          05 WS-STATUS-CALC      PIC X(02).
             88 CALC-OK          VALUE '00'.
             88 CALC-ERRO        VALUE '99'.
             88 TAXA-INVALIDA    VALUE '01'.
             88 PRAZO-INVALIDO   VALUE '02'.
             88 PRINCIPAL-INV    VALUE '03'.

       01 WS-ACUMULADOR          PIC S9(13)V9(06) COMP-3.

      *----------------------------------------------------------------*
      * Layout de entrada (LINKAGE para chamada via CALL)              *
      *----------------------------------------------------------------*
       LINKAGE SECTION.
       01 LS-INPUT.
          05 LS-PRINCIPAL        PIC 9(13)V9(02) COMP-3.
          05 LS-TAXA-ANUAL       PIC 9(05)V9(06) COMP-3.
          05 LS-PRAZO-MESES      PIC 9(03) COMP.
          05 LS-DATA-BASE        PIC 9(08).

       01 LS-OUTPUT.
          05 LS-MONTANTE-FINAL   PIC 9(13)V9(02) COMP-3.
          05 LS-JUROS-TOTAL      PIC 9(13)V9(02) COMP-3.
          05 LS-PARCELA-MENSAL   PIC 9(11)V9(02) COMP-3.
          05 LS-DATA-VENCIMENTO  PIC 9(08).
          05 LS-STATUS-RETORNO   PIC X(02).
          05 LS-MENSAGEM-ERRO    PIC X(60).

       PROCEDURE DIVISION USING LS-INPUT LS-OUTPUT.

      *----------------------------------------------------------------*
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-VALIDAR-INPUT
           IF CALC-OK
               PERFORM 3000-CALCULAR-TAXA-MENSAL
               PERFORM 4000-CALCULAR-MONTANTE
               PERFORM 5000-CALCULAR-PARCELA
               PERFORM 6000-CALCULAR-DATA-VENCIMENTO
               PERFORM 7000-FORMATAR-OUTPUT
           ELSE
               PERFORM 9000-TRATAR-ERRO
           END-IF
           STOP RUN.

      *----------------------------------------------------------------*
       1000-INICIALIZAR.
           MOVE SPACES TO LS-OUTPUT
           MOVE '00'   TO WS-STATUS-CALC
           MOVE ZERO   TO WS-FATOR-ACUM
                          WS-TAXA-MENSAL
                          WS-ACUMULADOR.

      *----------------------------------------------------------------*
       2000-VALIDAR-INPUT.
           IF LS-PRINCIPAL <= WS-ZERO
               MOVE '03' TO WS-STATUS-CALC
               MOVE 'Principal deve ser maior que zero'
                       TO LS-MENSAGEM-ERRO
               GO TO 2000-FIM
           END-IF

           IF LS-TAXA-ANUAL <= WS-ZERO
               MOVE '01' TO WS-STATUS-CALC
               MOVE 'Taxa anual deve ser maior que zero'
                       TO LS-MENSAGEM-ERRO
               GO TO 2000-FIM
           END-IF

           IF LS-PRAZO-MESES <= 0
               MOVE '02' TO WS-STATUS-CALC
               MOVE 'Prazo em meses deve ser maior que zero'
                       TO LS-MENSAGEM-ERRO
               GO TO 2000-FIM
           END-IF.
       2000-FIM.
           EXIT.

      *----------------------------------------------------------------*
      * Converte taxa anual para mensal: (1 + ta)^(1/12) - 1          *
      *----------------------------------------------------------------*
       3000-CALCULAR-TAXA-MENSAL.
           COMPUTE WS-TAXA-MENSAL ROUNDED =
               LS-TAXA-ANUAL / WS-MESES-ANO.

      *----------------------------------------------------------------*
      * Calcula montante: M = P * (1 + i)^n                           *
      * Implementado via loop para precisão COMP-3                    *
      *----------------------------------------------------------------*
       4000-CALCULAR-MONTANTE.
           MOVE WS-UM         TO WS-FATOR-ACUM
           MOVE ZERO          TO WS-CONT-MESES

           PERFORM VARYING WS-CONT-MESES FROM 1 BY 1
               UNTIL WS-CONT-MESES > LS-PRAZO-MESES
               COMPUTE WS-FATOR-ACUM ROUNDED =
                   WS-FATOR-ACUM * (WS-UM + WS-TAXA-MENSAL)
           END-PERFORM

           COMPUTE LS-MONTANTE-FINAL ROUNDED =
               LS-PRINCIPAL * WS-FATOR-ACUM

           COMPUTE LS-JUROS-TOTAL ROUNDED =
               LS-MONTANTE-FINAL - LS-PRINCIPAL.

      *----------------------------------------------------------------*
      * Calcula parcela mensal: PMT = P * i / (1 - (1+i)^-n)         *
      *----------------------------------------------------------------*
       5000-CALCULAR-PARCELA.
           IF LS-PRAZO-MESES = 0
               MOVE ZERO TO LS-PARCELA-MENSAL
               GO TO 5000-FIM
           END-IF

           COMPUTE WS-FATOR-TEMP ROUNDED =
               WS-UM / WS-FATOR-ACUM

           COMPUTE LS-PARCELA-MENSAL ROUNDED =
               LS-PRINCIPAL * WS-TAXA-MENSAL /
               (WS-UM - WS-FATOR-TEMP).
       5000-FIM.
           EXIT.

      *----------------------------------------------------------------*
      * Calcula data de vencimento: data_base + prazo_meses           *
      *----------------------------------------------------------------*
       6000-CALCULAR-DATA-VENCIMENTO.
           MOVE LS-DATA-BASE TO WS-DATA-VENCIMENTO
           MOVE LS-DATA-BASE (1:4) TO WS-ANO-BASE
           MOVE LS-DATA-BASE (5:2) TO WS-MES-BASE
           MOVE LS-DATA-BASE (7:2) TO WS-DIA-BASE

           ADD LS-PRAZO-MESES TO WS-MES-BASE

           PERFORM UNTIL WS-MES-BASE <= 12
               SUBTRACT 12 FROM WS-MES-BASE
               ADD 1 TO WS-ANO-BASE
           END-PERFORM

           STRING WS-ANO-BASE DELIMITED SIZE
                  WS-MES-BASE DELIMITED SIZE
                  WS-DIA-BASE DELIMITED SIZE
                  INTO LS-DATA-VENCIMENTO.

      *----------------------------------------------------------------*
       7000-FORMATAR-OUTPUT.
           MOVE WS-STATUS-CALC TO LS-STATUS-RETORNO
           MOVE SPACES         TO LS-MENSAGEM-ERRO.

      *----------------------------------------------------------------*
       9000-TRATAR-ERRO.
           MOVE WS-STATUS-CALC TO LS-STATUS-RETORNO
           MOVE ZERO           TO LS-MONTANTE-FINAL
                                  LS-JUROS-TOTAL
                                  LS-PARCELA-MENSAL.
