// Copy y datos de la landing v2. Precios y testimonio son de ejemplo:
// Dona está en pausa y esta página no cobra ni recoge datos.

export const PASOS = [
  {
    id: "01",
    nombre: "diagnóstico",
    titulo: "Diagnóstico",
    texto: "Dona lee tu contexto y tu negocio.",
  },
  {
    id: "02",
    nombre: "oportunidad",
    titulo: "Oportunidad",
    texto: "Detecta qué vale la pena hacer.",
  },
  {
    id: "03",
    nombre: "activo",
    titulo: "Activo",
    texto: "Prepara el borrador, la imagen o el mensaje.",
  },
  {
    id: "04",
    nombre: "acción",
    titulo: "Acción",
    texto: "Te propone qué hacer y cuánto cuesta.",
  },
  {
    id: "05",
    nombre: "permiso",
    titulo: "Permiso",
    texto: "Tú apruebas, editas o rechazas.",
  },
  {
    id: "06",
    nombre: "créditos",
    titulo: "Créditos",
    texto: "Se reservan; solo se cobran al ejecutar.",
  },
  {
    id: "07",
    nombre: "ejecución",
    titulo: "Ejecución",
    texto: "Se ejecuta con control y registro.",
  },
  {
    id: "08",
    nombre: "medición",
    titulo: "Medición",
    texto: "Mide lo que pasó de verdad.",
  },
  {
    id: "09",
    nombre: "reporte",
    titulo: "Reporte",
    texto: "Te lo cuenta claro, y propone lo siguiente.",
  },
] as const;

export const NIVELES = [
  {
    id: "bajo",
    etiqueta: "BAJO",
    celdas: 1,
    titulo: "Se ejecuta sola",
    texto: "Responder reseñas, recordatorios. Te avisamos después.",
  },
  {
    id: "medio",
    etiqueta: "MEDIO",
    celdas: 2,
    titulo: "Espera tu OK",
    texto: "Mensajes a clientes, publicaciones. Un toque para aprobar.",
  },
  {
    id: "alto",
    etiqueta: "ALTO",
    celdas: 3,
    titulo: "Confirmación dedicada",
    texto: "Precios, pagos, cambios difíciles de revertir.",
  },
  {
    id: "critico",
    etiqueta: "CRÍTICO",
    celdas: 4,
    titulo: "Bloqueada",
    texto: "Dona no lo hace. Punto.",
  },
] as const;

export const RESUMEN_MOVIL = [
  {
    id: "01",
    titulo: "Diagnóstico",
    texto: "Dona entiende tu negocio.",
  },
  {
    id: "02",
    titulo: "Permiso",
    texto: "Tú firmas lo importante.",
  },
  {
    id: "03",
    titulo: "Medición",
    texto: "Sabes qué funcionó.",
  },
] as const;

export const PREGUNTAS = [
  {
    id: "faq-sola",
    pregunta: "¿Dona hace cosas sin preguntarme?",
    respuesta:
      "Solo las de riesgo bajo, como responder reseñas, y siempre te avisa. Lo demás espera tu firma.",
  },
  {
    id: "faq-credito",
    pregunta: "¿Qué es un crédito?",
    respuesta:
      "Una unidad entera y prepaga. Se reserva cuando Dona propone una acción y se cobra solo si esa acción se ejecuta. Si la rechazas o falla, no se cobra. Los precios de esta página son un ejemplo.",
  },
  {
    id: "faq-whatsapp",
    pregunta: "¿Necesito WhatsApp?",
    respuesta:
      "No. Empiezas en el panel web y en la app. WhatsApp es un canal más. Gmail, Calendar y Sheets entran solo si tú los conectas, con el patrón preparar y confirmar.",
  },
  {
    id: "faq-datos",
    pregunta: "¿Qué pasa con mis datos?",
    respuesta:
      "Son tuyos. Puedes pedir una copia o pedir que los borremos. No los vendemos. El detalle está en la política de privacidad.",
  },
  {
    id: "pausa",
    pregunta: "¿Por qué Dona está en pausa?",
    respuesta:
      "La pausa es intencional: estamos cerrando la beta y no aceptamos compras nuevas. «Pedir acceso a la beta» no envía tus datos a ningún servidor.",
  },
] as const;
