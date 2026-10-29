import * as esbuild from "esbuild";

const options = {
  entryPoints: ["src/panel.ts"],
  outfile: "../custom_components/marketplace_discovery/frontend/panel.js",
  bundle: true,
  format: "esm",
  target: "es2022",
  minify: true,
  legalComments: "none",
  logLevel: "info",
};

if (process.argv.includes("--watch")) {
  const context = await esbuild.context({ ...options, minify: false, sourcemap: "inline" });
  await context.watch();
} else if (process.argv.includes("--dev")) {
  const context = await esbuild.context({ ...options, outfile: "dev/build/panel.js", minify: false, sourcemap: "inline" });
  await context.watch();
  const { port } = await context.serve({ servedir: "dev", host: "127.0.0.1", port: 8765 });
  console.log(`Dev harness on http://127.0.0.1:${port}/`);
} else {
  await esbuild.build(options);
}
