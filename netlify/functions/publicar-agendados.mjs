// Todo dia às 6h (horário de Brasília) pede um novo build ao Netlify,
// para que os posts agendados para a data entrem no ar sozinhos.
export default async () => {
  const hook = process.env.BUILD_HOOK_URL;
  if (!hook) {
    console.log("BUILD_HOOK_URL não configurada; nada a fazer.");
    return new Response("sem hook", { status: 200 });
  }
  const r = await fetch(hook, { method: "POST" });
  console.log(`Build solicitado: ${r.status}`);
  return new Response("ok");
};

export const config = { schedule: "0 9 * * *" };
