// landing/scripts/derive-dashboard-password.ts
// T1.4.B — CLI helper para derivar el password de dashboard de un usuario.
//
// Uso (desde landing/):
//   DASHBOARD_PASSWORD_SECRET=<el-mismo-secret-de-vercel> \
//     npx tsx scripts/derive-dashboard-password.ts cus_xxx
//
// El password derivado debe entregarse al usuario por canal seguro (Dona
// por WhatsApp es razonable). NO se persiste en ningún lado: si lo
// pierde, el owner lo regenera corriendo este script otra vez con el
// mismo customer_id.
//
// Este archivo no se importa desde el bundle de producción. Es solo una
// utilidad de operación.

import { deriveDashboardPassword } from "../lib/dashboard-auth";

const customerId = process.argv[2];

if (!customerId) {
  console.error(
    "Uso: tsx scripts/derive-dashboard-password.ts <stripe_customer_id>",
  );
  console.error("");
  console.error("Requiere DASHBOARD_PASSWORD_SECRET en el entorno.");
  console.error("Para tomar el customer_id desde Stripe Dashboard busca");
  console.error("en Customers el email del usuario y copia el cus_xxx.");
  process.exit(1);
}

const password = deriveDashboardPassword(customerId);

if (!password) {
  console.error(
    "Error: DASHBOARD_PASSWORD_SECRET no configurada o customer_id vacío.",
  );
  process.exit(2);
}

// Importante: el password se imprime tal cual a stdout. NO se loguea
// con console.log ni console.error si DASHBOARD_VERBOSE no está seteado,
// para evitar quedar en historial de scripts si el owner usa pipes.
process.stdout.write(password + "\n");
