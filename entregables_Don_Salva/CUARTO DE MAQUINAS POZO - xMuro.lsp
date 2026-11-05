;;; CUARTO DE MAQUINAS POZO - xMuro.lsp
;;; Inserta los 8 xMuro 15 (dinamicos, biblioteca de la oficina) en
;;; "CUARTO DE MAQUINAS POZO - OBRA GRIS - CUANT" (abrirlo en AutoCAD, APPLOAD a este archivo y escribir XMUROCUARTO).
;;; Funciones tomadas de mur.lsp y dbx.lsp (cuantificar-mamposteria-cad). Generado 2026-11-05.
(vl-load-com)
(defun cq:doc () (vla-get-activedocument (vlax-get-acad-object)))
(defun cq:setdyn (o nm val)
  (foreach p (vlax-invoke o 'GetDynamicBlockProperties)
    (if (= (vla-get-propertyname p) nm) (vlax-put p 'Value val))))
(defun cq:setatt (o tag val)
  (foreach a (vlax-invoke o 'GetAttributes)
    (if (= (vla-get-tagstring a) tag) (progn (vla-put-textstring a val) (vla-put-color a 250)))))
(defun cq:mur (blk sc lay x y ang len alt e1 e2 e3 px py / o)
  (setq o (vla-insertblock (vla-get-modelspace (cq:doc)) (vlax-3d-point (list x y 0.0)) blk sc sc sc 0.0))
  (vla-put-layer o lay)
  (cq:setdyn o "Longitud de Muro" len)
  (cq:setdyn o "Ang_Muro" ang)
  (cq:setdyn o "Position1 X" px)
  (cq:setdyn o "Position1 Y" py)
  (cq:setatt o "AL.TU" alt)
  (cq:setatt o "EP1" e1)
  (cq:setatt o "EP2" e2)
  (cq:setatt o "EP3" e3)
  (vla-get-handle o))
(defun cq:dbx ( / o v)
  (foreach v '("26" "25" "24" "23" "22" "21" "20")
    (if (not o)
      (if (not (vl-catch-all-error-p (setq o (vl-catch-all-apply 'vla-getinterfaceobject (list (vlax-get-acad-object) (strcat "ObjectDBX.AxDbDocument." v))))))
        o (setq o nil))))
  o)
(defun cq:steal (path names / dbx lst arr i r)
  (setq dbx (cq:dbx))
  (vla-open dbx path)
  (setq lst nil)
  (foreach n names
    (if (and (not (tblsearch "BLOCK" n)) (not (vl-catch-all-error-p (setq r (vl-catch-all-apply (function vla-item) (list (vla-get-blocks dbx) n))))))
      (setq lst (cons r lst))))
  (if lst
    (progn
      (setq arr (vlax-make-safearray vlax-vbobject (cons 0 (1- (length lst)))) i 0)
      (foreach o lst (vlax-safearray-put-element arr i o) (setq i (1+ i)))
      (vla-copyobjects dbx arr (vla-get-blocks (cq:doc)))))
  (vlax-release-object dbx)
  (mapcar (function (lambda (n) (if (tblsearch "BLOCK" n) n nil))) names))
(defun cq:unlock (n / l)
  (if (tblsearch "LAYER" n)
    (progn (setq l (vla-item (vla-get-layers (cq:doc)) n)) (vla-put-lock l :vlax-false) (vla-put-layeron l :vlax-true))
    (vla-add (vla-get-layers (cq:doc)) n)))
(defun c:XMUROCUARTO ( / lib ss n oldlay)
  (setq lib (findfile "lib_xMuro_10_15_20_30.dwg"))
  (if (not lib) (setq lib (getfiled "Biblioteca lib_xMuro_10_15_20_30.dwg (ruta sin acentos)" "" "dwg" 0)))
  (if (and lib (not (tblsearch "BLOCK" "xMuro 15"))) (cq:steal lib '("xMuro 15")))
  (if (not (tblsearch "BLOCK" "xMuro 15"))
    (princ "\n*** No se encontro el bloque xMuro 15: revisar la ruta de la biblioteca.")
    (progn
      (foreach n '("N1 Muro de 15cm" "N1 Muro de 15cm - Vano ventana" "N1 Muro de 15cm - Vano puerta") (cq:unlock n))
      (if (setq ss (ssget "_X" '((8 . "N1 Muro de 15cm*") (410 . "Model")))) (command "_.ERASE" ss ""))
      (setq oldlay (getvar "CLAYER"))
      (setvar "CLAYER" "N1 Muro de 15cm")
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm" 0.0000 2.2250 0.000000 4.3000 "3.00" "1" "A" "B" 2.2025 0.5530)   ; M1
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm" 4.2250 0.1500 1.570796 2.0000 "3.00" "A" "1" "2" 0.5300 1.2165)   ; M2
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm" 0.0750 0.1500 1.570796 2.0000 "3.00" "B" "1" "2" -0.4250 1.2165)   ; M3
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm" 0.0000 0.0750 0.000000 0.1500 "3.00" "2" "B" "V1" 0.1275 -0.1200)   ; M4
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm - Vano ventana" 0.1500 0.0750 0.000000 1.3500 "0.60" "2" "B" "A" 0.7275 -0.1200)   ; V1
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm" 1.5000 0.0750 0.000000 0.1500 "3.00" "2" "V1" "P1" 0.1275 -0.1200)   ; M5
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm - Vano puerta" 1.6500 0.0750 0.000000 1.0000 "2.10" "2" "B" "A" 0.5525 -0.1200)   ; P1
      (cq:mur "xMuro 15" 1.153846 "N1 Muro de 15cm" 2.6500 0.0750 0.000000 1.6500 "3.00" "2" "P1" "A" 0.8775 -0.1200)   ; M6
      (setvar "CLAYER" oldlay)
      (setq ss (ssget "_X" '((0 . "INSERT") (8 . "N1 Muro de 15cm*") (410 . "Model"))) n (if ss (sslength ss) 0))
      (princ (strcat "\nxMuro insertados: " (itoa n) " de 8 (6 muros + vano ventana + vano puerta). Largo total esperado 12.60 m."))
      (if (/= n 8) (princ "\n*** El conteo no cuadra: no guardar y revisar."))))
  (princ))
(princ "\nCargado. Escribir XMUROCUARTO.")
(princ)
