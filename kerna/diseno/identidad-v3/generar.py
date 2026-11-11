#!/usr/bin/env python3
"""Genera paletas.json, SVG sueltos, maquetas A/B y lámina de la identidad v3 de Kerna. Sin dependencias externas."""
import json, math, pathlib
AQUI = pathlib.Path(__file__).resolve().parent

ESTADOS = [  # clave, etiqueta (1-3 palabras), tono, modo (tarjetas|accion|nada), botones, texto accesible (de textos-finales.md)
 ("sin-info","Sin información","neutro","nada",[],"Aún no hay información de Kerna para este caso. Puedes clasificarlo como siempre."),
 ("generando","Preparando","azul","nada",[],"Kerna está buscando los artículos que podrían aplicarse. Suele tardar pocos minutos. Puedes seguir trabajando."),
 ("lista","Sugerencia lista","verde","tarjetas",["incluir","agregar"],"Sugerencia lista: tres artículos podrían aplicarse a este caso."),
 ("contingencia-modelo","Modo alternativo","ambar","tarjetas",["incluir","agregar"],"Sugerencia preparada con un modelo alternativo. Las citas fueron verificadas; revisa cada artículo con especial atención."),
 ("contingencia-busqueda","Búsqueda alternativa","ambar","tarjetas",["incluir","agregar"],"Normas buscadas con un método alternativo. Las citas fueron verificadas; puede faltar algún artículo."),
 ("revision-tiempo","Tiempo excedido","naranja","accion",["clasificar"],"Kerna tardó más de lo permitido y se detuvo. Este caso no tendrá sugerencia. Clasifícalo como siempre."),
 ("revision-citas","Citas no verificadas","violeta","accion",["clasificar"],"Las citas no coincidían con el texto vigente de las normas. Por seguridad no se muestra ningún artículo."),
 ("sin-normativa","Sin normativa","cian","accion",["clasificar"],"Kerna no encontró artículos que correspondan con claridad. Eso no significa que no exista normativa aplicable."),
 ("cadena-agotada","No se pudo","rojo","accion",["clasificar","codigo"],"Kerna no pudo preparar la sugerencia por una falla propia. Si se repite, reporta el código de seguimiento."),
 ("nucleo-no-disponible","No disponible","magenta","nada",[],"Kerna no está disponible. El caso quedó en espera y se seguirá intentando automáticamente."),
 ("conector-sin-nota","Sin respuesta","arena","accion",["clasificar"],"Kerna todavía no ha recibido este caso. Por ahora no habrá sugerencia."),
 ("conector-en-proceso","Recibido, sin respuesta","arena","accion",["clasificar"],"Kerna recibió el caso, pero la sugerencia no ha llegado en el tiempo habitual. Puede que llegue más tarde."),
 ("sin-conexion","Sin conexión","gris","accion",["reintentar"],"No se pudo actualizar: se perdió la conexión. Lo que ves puede estar desactualizado. Lo guardado no se pierde."),
 ("valorada","Clasificación guardada","fin","tarjetas",["guardar"],"Tu clasificación quedó guardada. Si necesitas corregirla, guarda una nueva: vale la última."),
]
# tono: (fondo, texto, acento)
TONOS_A = {"neutro":("#ECE5D5","#3B3650","#6F6A86"),"azul":("#DDE3F7","#1C2760","#3B4FB4"),"verde":("#D7EBD2","#123D1B","#2F7A33"),
 "ambar":("#F8E4AE","#4A3300","#8A5C00"),"naranja":("#FADCC2","#5A2A06","#A34D00"),"violeta":("#E8DAF1","#43185C","#8A3FB0"),
 "cian":("#D3E9EB","#0F3F46","#2A7480"),"rojo":("#F9D6CE","#6E1408","#B8321A"),"magenta":("#F6D7E6","#6B0F3B","#B02A6B"),
 "arena":("#E6DFCB","#433818","#7D6D45"),"gris":("#3A3F4C","#FFFFFF","#FFC9A8"),"fin":("#1F4F7A","#FFFFFF","#FFD36B")}
TONOS_B = {"neutro":("#1A2036","#E4E8F5","#8D98BC"),"azul":("#14244F","#E6EEFF","#7FA2FF"),"verde":("#0F3A2A","#E3FBEF","#4EE08F"),
 "ambar":("#3F3008","#FFF4D1","#FFC93C"),"naranja":("#44230A","#FFEBDD","#FF9A4D"),"violeta":("#2E1B52","#F3EAFF","#B58CFF"),
 "cian":("#0C3A42","#E1FAFF","#4FD8E8"),"rojo":("#4A1515","#FFE9E6","#FF6B5E"),"magenta":("#4A1236","#FFE8F4","#FF6FB5"),
 "arena":("#33301F","#F7F1DC","#C9BE8A"),"gris":("#2A2F3D","#F2F5FF","#9AA6C4"),"fin":("#CFFF5E","#0B1020","#0B1020")}
PAL = {
 "A":{"nombre":"Hilo","pagina":"#FFFFFF","panel":"#FBF6EA","tinta":"#1E1B2E","tonos":TONOS_A,
      "fijos":[["etiqueta grande: tinta / papel","#1E1B2E","#FBF6EA",4.5],["texto secundario / papel","#4A4560","#FBF6EA",4.5],
               ["tarjeta: tinta / fondo tarjeta","#1E1B2E","#FFFDF7",4.5],["botón: papel / tinta","#FBF6EA","#1E1B2E",4.5],
               ["hilo bermellón (gráficos) / papel","#B8321A","#FBF6EA",3.0],["hilo bermellón / tarjeta","#B8321A","#FFFDF7",3.0],
               ["número de artículo bermellón / tarjeta","#B8321A","#FFFDF7",4.5],["borde de tarjeta / papel","#6F6A86","#FBF6EA",3.0],["panel / página blanca","#FBF6EA","#FFFFFF",1.0]]},
 "B":{"nombre":"Núcleo","pagina":"#FFFFFF","panel":"#0B1020","tinta":"#F2F5FF","tonos":TONOS_B,
      "fijos":[["etiqueta grande / panel","#F2F5FF","#0B1020",4.5],["texto secundario / panel","#A9B4D6","#0B1020",4.5],
               ["tarjeta: texto / fondo tarjeta","#F2F5FF","#131B35",4.5],["botón: panel / lima","#0B1020","#CFFF5E",4.5],
               ["lima (gráficos) / panel","#CFFF5E","#0B1020",3.0],["lima / tarjeta","#CFFF5E","#131B35",3.0],["borde de tarjeta / panel","#5B6EB0","#0B1020",3.0],["panel / página blanca","#0B1020","#FFFFFF",3.0]]},
}
(AQUI/"paletas.json").write_text(json.dumps(PAL,ensure_ascii=False,indent=1))

# ---------------- primitivas SVG (viewBox 160x120) ----------------
def ovillo(cx,cy,r=26,extra=""):
    return (f'<g {extra}><circle class="of" cx="{cx}" cy="{cy}" r="{r}"/>'
     f'<path class="th2" d="M{cx-.72*r},{cy-.5*r} Q{cx},{cy+.1*r} {cx+.78*r},{cy-.4*r}"/>'
     f'<path class="th2" d="M{cx-.85*r},{cy+.1*r} Q{cx+.1*r},{cy+.7*r} {cx+.55*r},{cy+.6*r}"/>'
     f'<path class="th2" d="M{cx-.25*r},{cy-.9*r} Q{cx+.6*r},{cy-.1*r} {cx+.15*r},{cy+.95*r}"/></g>')
def etiqueta(x,y,w=46,h=38,dash=False,fill=True):
    d=' class="oz"' if dash else (' class="of"' if fill else ' class="o"')
    return (f'<path{d} d="M{x+11},{y} L{x+w},{y} L{x+w},{y+h} L{x+11},{y+h} L{x},{y+h/2} Z"/>'
            f'<circle class="{"oz" if dash else "o"}" cx="{x+10}" cy="{y+h/2}" r="2.6"/>')
def lineas(x,y,n=2,w=24,tacha=None):
    s=""
    for i in range(n):
        yy=y+i*9; s+=f'<path class="o2" d="M{x},{yy} h{w-(6 if i else 0)}"/>'
    return s
def reloj_arena(x,y):
    return (f'<g transform="translate({x},{y})"><path class="of" d="M-9,-13 H9 L1.5,0 L9,13 H-9 L-1.5,0 Z"/>'
            f'<path class="fa" d="M-4,-9 H4 L0,-3 Z"/><path class="fa" d="M-6,11 L0,3 L6,11 Z"/></g>')
def lupa(x,y,s=1):
    return (f'<g transform="translate({x},{y}) scale({s})"><circle class="of" r="12"/><path class="o" d="M9,9 L19,19" stroke-width="4"/></g>')
def sobre(x,y,dash=False):
    c="oz" if dash else "of"
    return (f'<g transform="translate({x},{y})"><rect class="{c}" x="0" y="0" width="40" height="28" rx="3"/>'
            f'<path class="{"oz" if dash else "o"}" d="M1,2 L20,17 L39,2"/></g>')
def check(cx,cy,r=9):
    return f'<g><circle class="fa" cx="{cx}" cy="{cy}" r="{r}"/><path class="chk" d="M{cx-.45*r},{cy+.05*r} L{cx-.1*r},{cy+.42*r} L{cx+.5*r},{cy-.4*r}"/></g>'
def hilo(d,cls="th",extra=""): return f'<path class="{cls}" d="{d}" {extra}/>'

def escena_A(k):
    B=ovillo(44,64)
    ghost=lambda: ovillo(44,64).replace('class="of"','class="oz"')
    if k=="sin-info":
        return (f'<g class="bob">{B}</g>'+hilo("M68,76 C84,90 92,70 108,84 S130,92 140,82","thz")+etiqueta(110,46,40,34,dash=True))
    if k=="generando":
        return (B+hilo("M68,60 C82,30 96,96 112,64","th flow")+etiqueta(108,46,44,36,dash=True)+
          '<g class="aguja"><path class="o" d="M104,94 L132,62" stroke-width="3"/><ellipse class="o2" cx="131" cy="63" rx="1.6" ry="3.4" transform="rotate(45 131 63)"/></g>')
    if k=="lista":
        return (B+hilo("M68,62 C84,40 96,88 118,64")+etiqueta(108,46,46,38)+
          '<path class="th" d="M117,64 q-6,-9 -12,-4 q4,8 12,4 q9,-8 14,-2 q-6,9 -14,2"/>'+check(146,48,10))
    if k=="contingencia-modelo":
        sp='<g class="bob"><rect class="of" x="26" y="82" width="30" height="8" rx="2"/><rect class="of" x="30" y="66" width="22" height="18"/><path class="th2" d="M30,72 h22 M30,78 h22"/><rect class="of" x="26" y="60" width="30" height="8" rx="2"/></g>'
        return (ghost()+sp+hilo("M52,74 C80,96 96,50 118,66")+etiqueta(108,48,46,38)+check(146,50,10))
    if k=="contingencia-busqueda":
        return (B+hilo("M68,64 C74,64 80,64 86,64")+hilo("M86,64 C96,64 100,66 110,66")+
          '<g class="bob">'+lupa(88,66,1.5)+'</g>'+etiqueta(114,48,40,36)+check(148,48,9))
    if k=="revision-tiempo":
        return (B+hilo("M68,64 C80,50 88,72 98,60")+hilo("M98,60 L112,68","thz")+reloj_arena(104,50).replace('translate','translate')+etiqueta(114,66,38,32,dash=True))
    if k=="revision-citas":
        return (ovillo(36,64,22)+hilo("M56,64 H80")+etiqueta(78,40,56,52)+lineas(98,56,3,30)+
          '<path class="err" d="M96,72 l28,-12"/>'+'<g class="bob">'+lupa(130,86,1.1)+'<path class="err" d="M126,82 l8,8 M134,82 l-8,8"/></g>')
    if k=="sin-normativa":
        return (B+hilo("M68,64 C86,64 100,80 112,72 C124,64 116,52 108,60","th")+
          '<circle class="oz" cx="118" cy="66" r="26"/><circle class="o2" cx="118" cy="66" r="21"/><rect class="of" x="112" y="38" width="12" height="8" rx="2" transform="translate(0,-6)"/>')
    if k=="cadena-agotada":
        return (B+hilo("M68,66 C76,66 80,62 86,64")+'<path class="th2" d="M86,64 l3,-4 m-3,4 l4,2 m-4,-2 l2,6"/>'+
          '<g class="chispa"><path class="err" d="M94,52 l6,10 l-6,2 l8,14"/></g>'+
          hilo("M104,70 C110,70 114,66 120,66")+'<path class="th2" d="M104,70 l-3,-4 m3,4 l-4,2 m4,-2 l-2,6"/>'+etiqueta(116,48,40,36))
    if k=="nucleo-no-disponible":
        return (f'<g class="resp">{ovillo(70,66,30)}</g>'+
          '<g class="zz"><text x="108" y="44" class="zt">z</text><text x="120" y="32" class="zt" style="font-size:20px">Z</text></g>'+
          '<g><circle class="of" cx="108" cy="86" r="14"/><rect class="fi" x="102" y="79" width="4.5" height="14" rx="1"/><rect class="fi" x="110.5" y="79" width="4.5" height="14" rx="1"/></g>')
    if k=="conector-sin-nota":
        return (B+hilo("M68,64 C82,52 92,76 102,64","th")+'<path class="thz" d="M102,64 L112,64"/>'+
          '<g class="bob">'+sobre(112,50,dash=True)+'</g>'+'<circle class="fa blink" cx="108" cy="64" r="3"/>')
    if k=="conector-en-proceso":
        return (B+hilo("M68,64 H92")+sobre(92,50)+'<path class="thz flowz" d="M132,64 C138,64 138,76 134,84"/>'+
          reloj_arena(140,96).replace('translate(140,96)','translate(128,92)')+etiqueta(106,84,0,0,dash=False).replace('<path','<path style="display:none"').replace('<circle','<circle style="display:none"'))
    if k=="sin-conexion":
        return (B+hilo("M68,64 C80,54 86,70 96,62","th")+'<path class="thz" d="M96,62 L108,64"/>'+
          '<g class="blink"><path class="o" d="M116,58 q14,-14 28,0"/><path class="o" d="M121,66 q9,-9 18,0"/><circle class="fi" cx="130" cy="74" r="3"/><path class="err" d="M112,92 L148,44" stroke-width="4"/></g>')
    if k=="valorada":
        return (B+hilo("M68,64 C84,44 96,86 116,64")+'<g transform="rotate(-6 132 66)">'+etiqueta(108,46,48,40)+lineas(124,56,2,22)+'</g>'+
          '<g class="sello"><circle class="fa" cx="138" cy="84" r="15"/><circle class="o2" cx="138" cy="84" r="11" stroke="var(--pf)"/><path class="chk" d="M131,84 l5,5 l9,-10"/></g>')
    raise KeyError(k)

def escena_B(k):
    cx,cy=80,60
    def nucleo(fill="fa",r=14,extra=""): return f'<circle class="{fill}" cx="{cx}" cy="{cy}" r="{r}" {extra}/>'
    def orb(r,cls="o2",extra=""): return f'<circle class="{cls}" cx="{cx}" cy="{cy}" r="{r}" {extra}/>'
    def sat(a,r,rad=5,cls="fa"):
        x=cx+r*math.cos(math.radians(a)); y=cy+r*math.sin(math.radians(a)); return f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="{rad}"/>'
    def spin(inner,dur,rev=False): return f'<g class="spin{" rev" if rev else ""}" style="animation-duration:{dur}s;transform-origin:{cx}px {cy}px">{inner}</g>'
    def arco(r,a0,a1,cls="th"):
        x0=cx+r*math.cos(math.radians(a0));y0=cy+r*math.sin(math.radians(a0));x1=cx+r*math.cos(math.radians(a1));y1=cy+r*math.sin(math.radians(a1))
        return f'<path class="{cls}" d="M{x0:.1f},{y0:.1f} A{r},{r} 0 {1 if (a1-a0)%360>180 else 0} 1 {x1:.1f},{y1:.1f}"/>'
    if k=="sin-info": return orb(46,"oz")+orb(28,"oz")+nucleo("o",12)+sat(300,46,3,"o")
    if k=="generando":
        return (orb(46,"o2")+orb(28,"o2")+spin(sat(20,46,5)+sat(200,46,4),5)+spin(sat(90,28,4),3.2,True)+'<g class="late">'+nucleo()+'</g>')
    if k=="lista":
        pts=[(-90,44),(30,44),(150,44)]
        ls="".join(f'<path class="th2" d="M{cx},{cy} L{cx+r*math.cos(math.radians(a)):.1f},{cy+r*math.sin(math.radians(a)):.1f}"/>' for a,r in pts)
        return orb(44,"o2")+ls+"".join(sat(a,r,7) for a,r in pts)+nucleo(r=15)+'<path class="chk2" d="M73,60 l5,5 l10,-11"/>'
    if k=="contingencia-modelo":
        return orb(46,"oz")+orb(30,"o2")+nucleo("o",14,'stroke-dasharray="3 3"')+spin(sat(0,30,8),6)+sat(250,46,5)+sat(110,46,5)
    if k=="contingencia-busqueda":
        return ('<ellipse class="oz" cx="80" cy="60" rx="62" ry="24" transform="rotate(-20 80 60)"/>'+orb(26,"o2")+nucleo(r=11)+
                spin('<ellipse class="th2" cx="80" cy="60" rx="62" ry="24" transform="rotate(-20 80 60)" stroke-dasharray="1 200" stroke-linecap="round" stroke-width="9"/>',7))
    if k=="revision-tiempo":
        ticks="".join(f'<path class="o2" d="M{cx+50*math.cos(math.radians(a)):.1f},{cy+50*math.sin(math.radians(a)):.1f} L{cx+55*math.cos(math.radians(a)):.1f},{cy+55*math.sin(math.radians(a)):.1f}"/>' for a in range(0,360,30))
        return ticks+orb(42,"o2")+arco(42,-90,150)+'<path class="th" d="M80,60 L80,36" stroke-linecap="butt"/><path class="th2" d="M80,60 L100,72"/>'+nucleo("o",5)+'<rect class="fa" x="106" y="97" width="22" height="5" rx="2"/>'
    if k=="revision-citas":
        return (orb(36,"o2")+'<circle class="th2" cx="92" cy="60" r="36" stroke-dasharray="4 3"/>'+nucleo("fa",9,'cx="86"')+
                '<circle class="o" cx="44" cy="60" r="5"/><circle class="o" cx="140" cy="60" r="5"/><path class="err" d="M70,98 l36,-8 M70,90 l36,-8" stroke-width="3.5"/>')
    if k=="sin-normativa":
        return (orb(46,"oz")+orb(28,"oz")+'<g class="radar" style="transform-origin:80px 60px"><path d="M80,60 L126,60 A46,46 0 0 0 112,27.5 Z" fill="var(--acc)" fill-opacity=".35"/><path class="th2" d="M80,60 L126,60"/></g>'+nucleo("o",9)+'<circle class="ping" cx="80" cy="60" r="9"/>')
    if k=="cadena-agotada":
        return (arco(40,-80,-10,"th")+arco(40,10,80,"th")+arco(40,100,170,"th")+arco(40,190,260,"th")+nucleo("o",13)+
                '<g class="chispa"><path class="err" d="M70,60 l7,-9 l-3,12 l9,-6 l-5,13" stroke-width="3"/></g>'+
                '<g class="late"><circle class="fa" cx="124" cy="22" r="3"/><circle class="fa" cx="34" cy="98" r="3"/><circle class="fa" cx="130" cy="96" r="2"/></g>')
    if k=="nucleo-no-disponible":
        return (orb(46,"oz")+f'<circle class="of" cx="{cx}" cy="{cy}" r="24"/><path class="th" d="M70,48 A15,15 0 1 0 90,48"/><path class="th" d="M80,42 L80,60"/>')
    if k=="conector-sin-nota":
        return (orb(32,"oz")+nucleo("o",11)+'<path class="th2" d="M6,60 H34" /><circle class="fa blink" cx="42" cy="60" r="4"/><path class="oz" d="M50,60 H60"/>')
    if k=="conector-en-proceso":
        return (orb(36,"o2")+nucleo("o",11,'class="o late"')+'<path class="th2" d="M6,60 H62"/><circle class="fa" cx="62" cy="60" r="4"/>'+
                '<g class="late">'+orb(26,"th2")+'</g><path class="th" d="M80,60 L80,44"/><path class="th2" d="M80,60 L92,66"/>'+sat(60,46,4,"o")+sat(180,46,4,"o"))
    if k=="sin-conexion":
        return (arco(44,-60,40,"th")+arco(44,100,200,"th")+nucleo("o",11)+sat(280,52,4,"o")+'<path class="err" d="M42,102 L118,18" stroke-width="4"/>'+'<g class="blink"><circle class="o2" cx="136" cy="96" r="4"/></g>')
    if k=="valorada":
        notches="".join(f'<path class="th2" d="M{cx+36*math.cos(math.radians(a)):.1f},{cy+36*math.sin(math.radians(a)):.1f} L{cx+47*math.cos(math.radians(a)):.1f},{cy+47*math.sin(math.radians(a)):.1f}" stroke-width="4"/>' for a in range(0,360,45))
        return orb(36,"th")+notches+nucleo(r=24)+'<path class="chk3" d="M69,60 l8,9 l15,-17"/>'
    raise KeyError(k)

# ---------- pictogramas de materia (48x48) ----------
def materia(cod,c):
    if c=="A":
        if cod=="karin": return ('<circle class="of" cx="15" cy="24" r="5"/><path class="of" d="M6,42 q9,-18 18,0 Z"/><circle class="of" cx="33" cy="24" r="5"/><path class="of" d="M24,42 q9,-18 18,0 Z"/>'
                                '<path class="th" d="M5,17 Q24,-3 43,17" stroke-dasharray="4 3"/><path class="fa" d="M24,6 l3,3 l-3,3 l-3,-3 Z"/>')
        if cod=="datos": return ('<path class="of" d="M24,3 L41,9 V24 C41,35 33,42 24,45 C15,42 7,35 7,24 V9 Z"/><path class="th2" d="M14,24 a10,10 0 0 1 20,0 M18,28 a6,6 0 0 1 12,0 M22,32 a2,2 0 0 1 4,0" stroke-dasharray="3 2.5"/><circle class="fa" cx="24" cy="19" r="2.4"/>')
        if cod=="penal": return ('<path class="of" d="M4,18 L24,5 L44,18 Z"/><path class="o" d="M11,22 V38 M21,22 V38 M31,22 V38 M41,22 V38"/><path class="o" d="M4,42 H44" stroke-width="4"/><path class="th" d="M24,18 v-4" /><circle class="fa" cx="24" cy="12" r="2.5"/>')
    else:
        if cod=="karin": return ('<circle class="o2" cx="15" cy="30" r="5"/><circle class="o2" cx="33" cy="30" r="5"/><path class="o2" d="M8,44 V38 q7,-6 14,0 V44 M26,44 V38 q7,-6 14,0 V44"/><path class="th2" d="M6,22 L24,4 L42,22"/><circle class="fa" cx="24" cy="4" r="3"/><circle class="fa" cx="6" cy="22" r="2.5"/><circle class="fa" cx="42" cy="22" r="2.5"/>')
        if cod=="datos": return ('<path class="o2" d="M24,3 L42,13.5 V34.5 L24,45 L6,34.5 V13.5 Z"/><circle class="o2" cx="24" cy="21" r="5"/><path class="o2" d="M24,26 V34"/><circle class="fa" cx="24" cy="3" r="2.8"/><circle class="fa" cx="42" cy="34.5" r="2.8"/><circle class="fa" cx="6" cy="34.5" r="2.8"/>')
        if cod=="penal": return ('<path class="o2" d="M24,4 L42,16 H6 Z"/><path class="o2" d="M12,20 V38 M24,20 V38 M36,20 V38 M5,42 H43"/><circle class="fa" cx="24" cy="4" r="3"/><circle class="fa" cx="12" cy="38" r="2.4"/><circle class="fa" cx="36" cy="38" r="2.4"/>')
def confianza(n,c):
    if c=="A":
        s=""
        for i in range(5):
            x=4+i*13
            s+=f'<path class="{"puntada" if i<n else "puntada vac"}" d="M{x},14 L{x+7},2"/>'
        return f'<svg viewBox="0 0 70 16" width="70" height="16" role="img" aria-label="Confianza {n} de 5">{s}</svg>'
    s=""
    for i in range(10):
        a0=-90+i*36+4;a1=a0+28
        p=lambda a:(18+13*math.cos(math.radians(a)),18+13*math.sin(math.radians(a)))
        (x0,y0),(x1,y1)=p(a0),p(a1)
        s+=f'<path class="{"seg" if i<n*2 else "seg vac"}" d="M{x0:.1f},{y0:.1f} A13,13 0 0 1 {x1:.1f},{y1:.1f}"/>'
    return f'<svg viewBox="0 0 36 36" width="40" height="40" role="img" aria-label="Confianza {n} de 5">{s}</svg>'
def svg(inner,vb,cls="",extra=""): return f'<svg viewBox="{vb}" class="{cls}" aria-hidden="true" {extra}>{inner}</svg>'

# ---------- logos ----------
LOGO_A=('<circle class="of" cx="24" cy="24" r="19"/><path class="th2" d="M9,17 Q24,29 38,19 M7,28 Q22,38 33,36 M18,6 Q34,22 26,43"/>'
        '<path class="th" d="M30,30 C36,24 38,38 44,44 M30,30 C38,30 42,22 45,14" stroke-width="4"/>')
LOGO_B=('<circle class="o2" cx="24" cy="24" r="20"/><circle class="o2" cx="24" cy="24" r="12"/><circle class="fa" cx="24" cy="24" r="5"/><circle class="fa" cx="38" cy="10" r="3.5"/><path class="th2" d="M24,24 L38,10"/>')

# ---------- CSS ----------
FONTS="""
@font-face{font-family:Fraunces;font-weight:700;src:url(../fuentes/fraunces-latin-700-normal.woff2)}
@font-face{font-family:Fraunces;font-weight:400;font-style:italic;src:url(../fuentes/fraunces-latin-400-italic.woff2)}
@font-face{font-family:Figtree;font-weight:500;src:url(../fuentes/figtree-latin-500-normal.woff2)}
@font-face{font-family:Figtree;font-weight:700;src:url(../fuentes/figtree-latin-700-normal.woff2)}
@font-face{font-family:Unbounded;font-weight:700;src:url(../fuentes/unbounded-latin-700-normal.woff2)}
@font-face{font-family:Unbounded;font-weight:500;src:url(../fuentes/unbounded-latin-500-normal.woff2)}
@font-face{font-family:"JetBrains Mono";font-weight:500;src:url(../fuentes/jetbrains-mono-latin-500-normal.woff2)}
"""
ANIM="""
@keyframes flow{to{stroke-dashoffset:-24}} @keyframes bob{50%{transform:translateY(-3px)}} @keyframes spin{to{transform:rotate(360deg)}}
@keyframes late{50%{opacity:.55}} @keyframes blink{50%{opacity:.25}} @keyframes aguja{50%{transform:translate(4px,-5px)}}
@keyframes ping{from{r:9;opacity:.9}to{r:46;opacity:0}} @keyframes zz{50%{transform:translateY(-4px);opacity:.6}} @keyframes sello{0%{transform:scale(1.25);opacity:0}60%{transform:scale(.95);opacity:1}100%{transform:scale(1)}}
@keyframes chispa{0%,100%{opacity:1}50%{opacity:.2}}
.flow,.flowz{stroke-dasharray:6 6;animation:flow 1.1s linear infinite}.flowz{animation-duration:2.4s}
.bob{animation:bob 3s ease-in-out infinite}.resp{animation:bob 4.5s ease-in-out infinite}.aguja{animation:aguja 1.6s ease-in-out infinite}
.spin{animation:spin 6s linear infinite}.spin.rev{animation-direction:reverse}.late{animation:late 2.2s ease-in-out infinite}.blink{animation:blink 1.4s steps(2) infinite}
.radar{animation:spin 3.4s linear infinite}.ping{fill:none;stroke:var(--acc);stroke-width:1.5;animation:ping 2.6s ease-out infinite}
.zz{animation:zz 2.6s ease-in-out infinite}.sello{transform-origin:138px 84px;animation:sello .9s ease-out both}.chispa{animation:chispa .9s steps(2) infinite}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""
CSS_ART="""
svg{display:block;overflow:visible}.o,.o2,.of,.oz,.th,.th2,.thz,.err,.chk,.chk2,.chk3,.puntada,.seg{fill:none;stroke-linecap:round;stroke-linejoin:round}
.o{stroke:var(--pi);stroke-width:3}.o2{stroke:var(--pi);stroke-width:2}.of{stroke:var(--pi);stroke-width:3;fill:var(--pf)}.oz{stroke:var(--pi);stroke-width:2;stroke-dasharray:4 4;fill:none}
.th{stroke:var(--acc);stroke-width:4}.th2{stroke:var(--acc);stroke-width:2.5}.thz{stroke:var(--acc);stroke-width:3;stroke-dasharray:2 6}.err{stroke:var(--acc);stroke-width:3}
.fa{fill:var(--acc)}.fi{fill:var(--pi)}.chk{stroke:var(--pf);stroke-width:3}.chk2{stroke:var(--pf);stroke-width:4}.chk3{stroke:var(--pf);stroke-width:7}
.zt{font:700 14px Fraunces,serif;fill:var(--acc)}.puntada{stroke:var(--acc);stroke-width:3.2}.puntada.vac{stroke:var(--pi);stroke-width:1.6;stroke-dasharray:1.5 3;opacity:.7}
.seg{stroke:var(--acc);stroke-width:3.4;stroke-linecap:butt}.seg.vac{stroke:var(--pi);stroke-width:2;opacity:.35}
"""
def vars_estado(tono,c):
    f,t,a=(PAL[c]["tonos"][tono])
    oscuro = tono in("gris","fin") if c=="A" else tono=="fin"
    if c=="A":
        pi="#FFFFFF" if oscuro else "#1E1B2E"; pf=f if oscuro else "#FBF6EA"
    else:
        pi="#0B1020" if tono=="fin" else t; pf=f if tono!="fin" else "#CFFF5E"
        if tono!="fin": pf="#0B1020"
        if tono=="fin": pf="#CFFF5E"
    return f"--fondo:{f};--txt:{t};--acc:{a};--pi:{pi};--pf:{pf}"

CSS_A=FONTS+ANIM+CSS_ART+"""
*{box-sizing:border-box}body{margin:0;background:#fff;font:500 16px Figtree,sans-serif;color:#1E1B2E;padding:24px 0}
.bloque{width:790px;margin:0 auto 28px;background:#FBF6EA;border:3px solid #1E1B2E;border-radius:6px 28px 6px 28px;padding:26px 30px 20px;position:relative}
.bloque::before{content:"";position:absolute;inset:7px;border:2px dashed #6F6A86;border-radius:3px 22px 3px 22px;pointer-events:none}
.cab{display:flex;align-items:center;gap:10px;position:relative}.cab svg{width:34px;height:34px;--pi:#1E1B2E;--pf:#FBF6EA;--acc:#B8321A}
.marca{font:italic 400 26px Fraunces,serif;letter-spacing:.2px}.ficha{margin-left:auto;display:inline-flex;align-items:center;gap:8px;padding:5px 14px 5px 10px;border-radius:4px 14px 4px 14px;background:var(--fondo);color:var(--txt);font-weight:700;font-size:13px;letter-spacing:.8px;text-transform:uppercase}
.ficha i{width:9px;height:9px;border-radius:50%;background:var(--acc);display:inline-block}
.hero{display:flex;align-items:center;gap:26px;margin:18px 0 6px;position:relative}
.parche{flex:none;width:210px;height:158px;border-radius:78px 18px 78px 18px;background:var(--fondo);display:grid;place-items:center}.parche svg{width:178px;height:134px}
.etq{font:700 46px/1.02 Fraunces,serif;letter-spacing:-.5px;margin:0}.meta{font-size:13px;letter-spacing:1.4px;text-transform:uppercase;color:#4A4560;margin:8px 0 0;font-weight:700}
.tarjetas{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:16px 0 4px;position:relative}
.tarjeta{background:#FFFDF7;border:2px solid #6F6A86;border-radius:4px 20px 4px 20px;padding:14px 14px 12px;position:relative;display:grid;gap:4px}
.tarjeta .mat{width:50px;height:50px;--pi:#1E1B2E;--pf:#FBF6EA;--acc:#B8321A}
.num{font:700 66px/.9 Fraunces,serif;color:#B8321A;margin:2px 0 0}.num small{font:700 13px Figtree;letter-spacing:1px;color:#4A4560;margin-right:4px;text-transform:uppercase}
.norma{font-weight:700;font-size:17px}.ley{font-size:13px;color:#4A4560;letter-spacing:.5px}
.tarjeta .conf{--pi:#1E1B2E;--acc:#B8321A;margin-top:4px}.vis{position:absolute;right:10px;top:10px;width:26px;height:26px;--acc:#2F7A33;--pf:#FFFDF7}
.acciones{display:flex;gap:12px;margin:16px 0 4px;position:relative;flex-wrap:wrap}.btn{display:inline-flex;gap:8px;align-items:center;font:700 16px Figtree;padding:11px 20px 11px 14px;border-radius:4px 16px 4px 16px;border:2px solid #1E1B2E;background:#1E1B2E;color:#FBF6EA}
.btn.sec{background:transparent;color:#1E1B2E}.btn svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2.6;stroke-linecap:round}
.pie{display:flex;align-items:center;gap:8px;margin-top:14px;font-size:13px;color:#4A4560;font-weight:700;position:relative}.pie svg{width:22px;height:22px;--pi:#4A4560;--pf:#FBF6EA;--acc:#B8321A}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
"""
CSS_B=FONTS+ANIM+CSS_ART+"""
*{box-sizing:border-box}body{margin:0;background:#fff;font:500 15px "JetBrains Mono",monospace;color:#F2F5FF;padding:24px 0}
.bloque{width:790px;margin:0 auto 28px;background:#0B1020;border-radius:4px;padding:0 0 18px;position:relative;overflow:hidden;background-image:linear-gradient(#131B35 1px,transparent 1px),linear-gradient(90deg,#131B35 1px,transparent 1px);background-size:26px 26px}
.cab{display:flex;align-items:center;gap:12px;padding:14px 22px;border-bottom:1px solid #2B3763;background:#0B1020}.cab svg{width:30px;height:30px;--pi:#F2F5FF;--pf:#0B1020;--acc:#CFFF5E}
.marca{font:700 15px Unbounded,sans-serif;letter-spacing:6px;text-transform:uppercase}.ficha{margin-left:auto;display:inline-flex;align-items:center;gap:8px;padding:6px 12px;background:var(--fondo);color:var(--txt);border:1px solid var(--acc);font-size:12px;letter-spacing:1px;text-transform:uppercase}
.ficha i{width:8px;height:8px;background:var(--acc);display:inline-block;transform:rotate(45deg)}
.hero{display:grid;grid-template-columns:220px 1fr;align-items:center;gap:22px;padding:22px 26px 6px}
.parche{width:220px;height:165px;background:var(--fondo);clip-path:polygon(14% 0,100% 0,100% 86%,86% 100%,0 100%,0 14%);display:grid;place-items:center;box-shadow:inset 0 0 0 1px var(--acc)}.parche svg{width:190px;height:142px}
.etq{font:700 27px/1.15 Unbounded,sans-serif;letter-spacing:.5px;text-transform:uppercase;margin:0}.meta{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#A9B4D6;margin:10px 0 0}
.tarjetas{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding:12px 26px 0}
.tarjeta{background:#131B35;border:1px solid #5B6EB0;padding:14px;position:relative;display:grid;gap:6px;clip-path:polygon(0 0,calc(100% - 16px) 0,100% 16px,100% 100%,0 100%)}
.tarjeta .mat{width:44px;height:44px;--pi:#F2F5FF;--acc:#CFFF5E;--pf:#131B35}.tarjeta .conf{position:absolute;right:12px;bottom:12px;--pi:#F2F5FF;--acc:#CFFF5E}
.num{font:700 56px/1 Unbounded,sans-serif;color:#F2F5FF;margin:4px 0 0}.num small{font:500 11px "JetBrains Mono";letter-spacing:2px;color:#A9B4D6;margin-right:6px}
.norma{font:700 11px Unbounded,sans-serif;text-transform:uppercase;letter-spacing:.3px;max-width:150px}.ley{font-size:12px;color:#A9B4D6}.vis{position:absolute;right:12px;top:12px;width:24px;height:24px;--acc:#CFFF5E;--pf:#131B35}
.acciones{display:flex;gap:10px;padding:16px 26px 0;flex-wrap:wrap}.btn{display:inline-flex;gap:8px;align-items:center;font:700 13px Unbounded,sans-serif;text-transform:uppercase;letter-spacing:.5px;padding:12px 18px;background:#CFFF5E;color:#0B1020;border:1px solid #CFFF5E;clip-path:polygon(0 0,calc(100% - 10px) 0,100% 10px,100% 100%,0 100%)}
.btn.sec{background:transparent;color:#F2F5FF;border-color:#5B6EB0}.btn svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2.6;stroke-linecap:round}
.pie{display:flex;align-items:center;gap:8px;padding:16px 26px 0;font-size:12px;color:#A9B4D6;letter-spacing:1px;text-transform:uppercase}.pie svg{width:20px;height:20px;--pi:#A9B4D6;--pf:#0B1020;--acc:#CFFF5E}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
"""
BTN={"incluir":("Incluir",'<path d="M4 11l5 5 9-10"/>',False),"agregar":("Agregar",'<path d="M11 4v14M4 11h14"/>',True),"clasificar":("Clasificar",'<path d="M4 6h14M4 11h14M4 16h8"/>',False),
 "codigo":("Copiar código",'<rect x="7" y="7" width="11" height="11" rx="2"/><path d="M4 14V5a1 1 0 0 1 1-1h9"/>',True),"reintentar":("Reintentar",'<path d="M18 11a7 7 0 1 1-2.5-5.4M18 3v5h-5"/>',False),"guardar":("Guardar",'<path d="M4 11l5 5 9-10"/>',False)}
CARDS=[("karin","Ley Karin","21.643","2",5),("datos","Datos personales","19.628","4",3),("penal","Resp. penal","20.393","3",2)]
def pie_icon(c):
    return ('<circle class="of" cx="12" cy="8" r="4"/><path class="of" d="M3,22 q9,-16 18,0 Z"/><path class="th2" d="M12,12 v4"/>' if c=="A" else '<circle class="o2" cx="12" cy="12" r="9"/><circle class="fa" cx="12" cy="12" r="3"/><path class="th2" d="M12,3 V0"/>')

def bloque(c,e,ident=True):
    k,lab,tono,modo,btns,sr=e
    esc=(escena_A if c=="A" else escena_B)(k)
    f,t,a=PAL[c]["tonos"][tono]
    cards=""
    if modo=="tarjetas":
        for cod,nom,ley,art,n in CARDS:
            vis=f'<svg viewBox="0 0 24 24" class="vis">{check(12,12,11)}</svg>' if k=="valorada" else ""
            cards+=(f'<div class="tarjeta" role="group" aria-label="{nom}, artículo {art}, confianza {n} de 5">{vis}{svg(materia(cod,c),"0 0 48 48","mat")}'
                    f'<div class="num"><small>Art.</small>{art}</div><div class="norma">{nom}</div><div class="ley">Ley {ley}</div>'
                    f'<div class="conf">{confianza(n,c)}</div></div>')
        cards=f'<div class="tarjetas">{cards}</div>'
    ac=""
    if btns:
        ac='<div class="acciones">'+"".join(f'<span class="btn{" sec" if BTN[b][2] else ""}"><svg viewBox="0 0 22 22">{BTN[b][1]}</svg>{BTN[b][0]}</span>' for b in btns)+'</div>'
    meta={"lista":"3 artículos","contingencia-modelo":"3 artículos","contingencia-busqueda":"3 artículos","valorada":"3 aplicados"}.get(k,"")
    meta=f'<p class="meta">{meta}</p>' if meta else ""
    return (f'<section class="bloque" id="{k}" style="{vars_estado(tono,c)}" aria-label="Kerna: {lab}"><p class="sr">{sr}</p>'
      f'<div class="cab">{svg(LOGO_A if c=="A" else LOGO_B,"0 0 48 48")}<span class="marca">Kerna</span><span class="ficha"><i></i>{lab}</span></div>'
      f'<div class="hero"><div class="parche">{svg(esc,"0 0 160 120")}</div><div><h2 class="etq">{lab}</h2>{meta}</div></div>{cards}{ac}'
      f'<div class="pie">{svg(pie_icon(c),"0 0 24 24")}Apoyo, no dictamen</div></section>')

for c in "AB":
    css=CSS_A if c=="A" else CSS_B
    body="".join(bloque(c,e) for e in ESTADOS)
    (AQUI/"maqueta"/f"maqueta-{c}.html").write_text(f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kerna identidad v3 {PAL[c]["nombre"]}</title><style>{css}</style></head><body>{body}</body></html>')
    for e in ESTADOS:  # SVG suelto por estado
        f_,t_,a_=PAL[c]["tonos"][e[2]]
        st=vars_estado(e[2],c)
        (AQUI/"svg"/f"{c}-{e[0]}.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 120" width="320" height="240" style="{st}"><style>{CSS_ART}</style>{(escena_A if c=="A" else escena_B)(e[0])}</svg>')
    (AQUI/"svg"/f"{c}-logo.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="96" height="96" style="--pi:{"#1E1B2E" if c=="A" else "#F2F5FF"};--pf:{"#FBF6EA" if c=="A" else "#0B1020"};--acc:{"#B8321A" if c=="A" else "#CFFF5E"}"><style>{CSS_ART}</style>{LOGO_A if c=="A" else LOGO_B}</svg>')

# ---------- lámina ----------
def col(c):
    p=PAL[c]; dark=c=="B"
    celdas="".join(f'<div class="cel" style="{vars_estado(e[2],c)}"><div class="pa">{svg((escena_A if c=="A" else escena_B)(e[0]),"0 0 160 120")}</div><b>{e[1]}</b></div>' for e in ESTADOS)
    mats="".join(f'<div class="mt">{svg(materia(cd,c),"0 0 48 48","m")}<b>{n}</b></div>' for cd,n,_,_,_ in CARDS)
    return celdas,mats
LAM_CSS=FONTS.replace("../fuentes","fuentes")+ANIM+CSS_ART+"""
*{box-sizing:border-box}body{margin:0;background:#E9E6EF;font:500 15px Figtree,sans-serif;padding:36px;color:#1E1B2E;width:1872px}
h1{font:700 34px Fraunces,serif;margin:0 0 4px}.sub{margin:0 0 24px;color:#4A4560}.cols{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.col{border-radius:14px;padding:26px}.ca{background:#FBF6EA}.cb{background:#0B1020;color:#F2F5FF}
.col h2{margin:0;font-size:44px;line-height:1}.ca h2{font-family:Fraunces,serif}.cb h2{font-family:Unbounded,sans-serif;text-transform:uppercase;font-size:34px}
.lin{margin:8px 0 18px;font-size:16px}.cb .lin{font-family:"JetBrains Mono";font-size:14px;color:#A9B4D6}
.top{display:flex;gap:20px;align-items:center;margin-bottom:16px}.logo{width:96px;height:96px}.ca .logo{--pi:#1E1B2E;--pf:#FBF6EA;--acc:#B8321A}.cb .logo{--pi:#F2F5FF;--pf:#0B1020;--acc:#CFFF5E}
.sw{display:flex;gap:6px;margin:10px 0}.sw i{width:44px;height:28px;border-radius:4px;border:1px solid #8884}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.cel{text-align:center}.pa{background:var(--fondo);border-radius:20px;padding:6px}.ca .pa{border-radius:40px 10px 40px 10px}.cb .pa{border-radius:0;clip-path:polygon(12% 0,100% 0,100% 88%,88% 100%,0 100%,0 12%)}
.cel svg{width:100%;height:auto}.cel b{display:block;margin-top:6px;font-size:14px}.cb .cel b{font-family:"JetBrains Mono";text-transform:uppercase;font-size:11px;letter-spacing:1px}
.mts{display:flex;gap:24px;margin:20px 0}.mt{display:flex;align-items:center;gap:10px}.mt .m{width:56px;height:56px}.ca .m{--pi:#1E1B2E;--pf:#FBF6EA;--acc:#B8321A}.cb .m{--pi:#F2F5FF;--pf:#0B1020;--acc:#CFFF5E}
.ca .conf{--pi:#1E1B2E;--acc:#B8321A}.cb .conf{--pi:#F2F5FF;--acc:#CFFF5E}
.tipo{margin:14px 0 6px;display:flex;align-items:baseline;gap:22px}.ca .tipo b{font:700 72px Fraunces,serif;color:#B8321A}.cb .tipo b{font:700 56px Unbounded,sans-serif}
"""
def lamina():
    out=""
    desc={"A":("Hilo","Un solo hilo bermellón enhebra los hechos de la denuncia hasta la etiqueta de la norma: cada estado es el hilo en un punto distinto de su recorrido.","Fraunces 700 + Figtree"),
          "B":("Núcleo","Kerna es un núcleo con órbitas: los artículos son satélites que se acoplan al núcleo cuando encajan; cada estado es una configuración orbital.","Unbounded 700 + JetBrains Mono")}
    for c in "AB":
        celdas,mats=col(c); n,l,tp=desc[c]
        sw="".join(f'<i style="background:{PAL[c]["tonos"][t][2]}"></i>' for t in ("verde","azul","ambar","naranja","rojo","cian","violeta"))
        base=(PAL[c]["panel"],PAL[c]["tinta"],"#B8321A" if c=="A" else "#CFFF5E")
        sw=f'<i style="background:{base[0]}"></i><i style="background:{base[1]}"></i><i style="background:{base[2]}"></i>'+sw
        lg=LOGO_A if c=="A" else LOGO_B
        conf="".join(f'<div class="mt">{confianza(n_,c).replace("<svg","<svg class=conf")}</div>' for n_ in (5,3,1))
        tip='<b>Art. 2</b><span>Ley Karin</span>'
        out+=(f'<div class="col c{c.lower()}"><div class="top">{svg(lg,"0 0 48 48","logo")}<div><h2>{c} · {n}</h2><div class="lin">{tp}</div></div></div>'
              f'<div class="lin">{l}</div><div class="sw">{sw}</div><div class="tipo">{tip}</div>'
              f'<div class="mts">{mats}{conf}</div><div class="grid">{celdas}</div></div>')
    (AQUI/"lamina.html").write_text(f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Lámina identidad v3</title><style>{LAM_CSS}</style></head><body><h1>Kerna · identidad v3: dos conceptos</h1><p class="sub">14 estados, pictogramas de materia (Ley Karin, datos personales, responsabilidad penal) y confianza como gráfico</p><div class="cols">{out}</div></body></html>')
lamina()
print("ok")
