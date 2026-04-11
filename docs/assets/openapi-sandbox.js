/**
 * Static OpenAPI explorer: validate application/json bodies with Ajv (no network).
 * Loaded from openapi-explorer.html.
 *
 * Swagger loads the contract via `url` so `$ref` bases are correct. On `file://`, a blob URL is used
 * so internal `#/components/...` refs resolve (see inline comments in mount).
 * A dereferenced clone is used only for Ajv (concrete request-body schemas).
 */
import $RefParser from "https://esm.sh/@apidevtools/json-schema-ref-parser@11.7.2";
import Ajv2020 from "https://esm.sh/ajv@8.12.0/dist/2020.js";
import addFormats from "https://esm.sh/ajv-formats@2.1.1";

/** Incremented before a synthetic data: response; responseInterceptor decrements (handles empty res.url). */
let pendingSyntheticResponses = 0;

function matchPathTemplate(paths, pathname) {
  if (!paths) {
    return null;
  }
  const clean = pathname.replace(/\/$/, "") || "/";
  if (paths[pathname] !== undefined) {
    return pathname;
  }
  if (paths[clean] !== undefined) {
    return clean;
  }
  const pathParts = clean.split("/").filter(Boolean);
  for (const template of Object.keys(paths)) {
    const parts = template.split("/").filter(Boolean);
    if (parts.length !== pathParts.length) {
      continue;
    }
    let ok = true;
    for (let i = 0; i < parts.length; i++) {
      if (parts[i].startsWith("{") && parts[i].endsWith("}")) {
        continue;
      }
      if (parts[i] !== pathParts[i]) {
        ok = false;
        break;
      }
    }
    if (ok) {
      return template;
    }
  }
  return null;
}

function getJsonBodySchema(spec, pathTemplate, methodLower) {
  const op = spec.paths?.[pathTemplate]?.[methodLower];
  const content = op?.requestBody?.content;
  if (!content || !content["application/json"]) {
    return null;
  }
  return content["application/json"].schema ?? null;
}

function buildAjvFromComponents(spec) {
  const ajv = new Ajv2020({
    allErrors: true,
    strict: false,
    verbose: true,
  });
  addFormats(ajv);
  const schemas = spec.components?.schemas;
  if (!schemas) {
    return ajv;
  }
  for (const [name, schema] of Object.entries(schemas)) {
    const id = "#/components/schemas/" + name;
    try {
      const withId =
        schema && typeof schema === "object" && !schema.$id ? Object.assign({}, schema, { $id: id }) : schema;
      ajv.addSchema(withId);
    } catch (e) {
      console.warn("[openapi-validator] addSchema skipped:", name, e);
    }
  }
  return ajv;
}

function compileBodyValidator(ajv, schema) {
  if (!schema) {
    return null;
  }
  if (schema.$ref) {
    const fn = ajv.getSchema(schema.$ref);
    if (typeof fn === "function") {
      return fn;
    }
  }
  try {
    return ajv.compile(schema);
  } catch (e) {
    console.warn("[openapi-validator] compile failed:", e);
    return null;
  }
}

function requestPathname(req) {
  const raw = req && req.url;
  if (!raw || typeof raw !== "string") {
    return null;
  }
  if (raw.startsWith("blob:")) {
    return null;
  }
  try {
    const u = new URL(raw, window.location.href);
    return u.pathname || "/";
  } catch {
    return null;
  }
}

function isOpenApiDocumentRequest(req, specLoadUrl) {
  try {
    const raw = req && req.url;
    if (!raw || typeof raw !== "string") {
      return false;
    }
    const u = new URL(raw, window.location.href);
    const s = new URL(specLoadUrl, window.location.href);
    u.hash = "";
    s.hash = "";
    return u.href === s.href;
  } catch {
    return false;
  }
}

function validationRequestInterceptor(spec, ajv, specLoadUrl) {
  return function (req) {
    if (isOpenApiDocumentRequest(req, specLoadUrl)) {
      return req;
    }

    const pathname = requestPathname(req);
    const pathTemplate = pathname ? matchPathTemplate(spec.paths, pathname) : null;
    const method = (req.method || "get").toLowerCase();
    const schema = pathTemplate ? getJsonBodySchema(spec, pathTemplate, method) : null;
    const validateFn = compileBodyValidator(ajv, schema);

    if (!validateFn) {
      const hint =
        ["get", "head", "delete"].indexOf(method) >= 0 || !pathTemplate
          ? "This operation has no JSON request body in the OpenAPI spec (e.g. GET or no body)."
          : "No application/json schema for this operation.";
      window.alert("[Validator] " + hint + " Nothing was sent.");
      return Promise.reject(new Error("Validator: no JSON body schema for this operation."));
    }

    const raw = req.body;
    if (raw === undefined || raw === null || String(raw).trim() === "") {
      window.alert("[Validator] Empty body. Paste JSON in the request body field. Nothing was sent.");
      return Promise.reject(new Error("Validator: empty body."));
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      window.alert("[Validator] Invalid JSON: " + (e && e.message ? e.message : e));
      return Promise.reject(e);
    }

    const ok = validateFn(data);
    if (!ok) {
      const msg = validateFn.errors ? ajv.errorsText(validateFn.errors, { separator: "\n" }) : "unknown";
      window.alert("[Validator] Does not match schema (openapi-baseline.json):\n\n" + msg);
      return Promise.reject(new Error("Validator: validation failed."));
    }

    const payload = JSON.stringify({
      ok: true,
      message: "JSON matches this operation’s request body schema. No HTTP request was sent.",
    });
    const dataUrl = "data:application/json;charset=utf-8," + encodeURIComponent(payload);
    pendingSyntheticResponses += 1;
    return Promise.resolve(
      new Request(dataUrl, {
        method: "GET",
        headers: new Headers({ Accept: "application/json" }),
      }),
    );
  };
}

function plainTextOkResponse() {
  return new Response("Valid: JSON matches the OpenAPI request body schema. No HTTP request was sent.", {
    status: 200,
    statusText: "OK",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

export async function mountOpenAPIExplorer() {
  const specFileUrl = new URL("openapi/openapi-baseline.json", window.location.href).href;
  const res = await fetch(specFileUrl);
  if (!res.ok) {
    throw new Error("HTTP " + res.status);
  }
  const specRaw = await res.json();
  const specClone = JSON.parse(JSON.stringify(specRaw));
  let specResolved = specRaw;
  let derefOk = false;
  try {
    specResolved = await $RefParser.dereference(specClone);
    derefOk = true;
  } catch (e) {
    console.warn("[openapi-validator] $RefParser.dereference failed:", e);
    if (window.location.protocol === "file:") {
      throw new Error(
        "Could not resolve OpenAPI $ref for this page (see console). " +
          "Try: cd docs && python -m http.server 8765 → http://127.0.0.1:8765/openapi-explorer.html",
      );
    }
  }

  const specForValidation = derefOk ? specResolved : specRaw;
  const ajv = buildAjvFromComponents(specForValidation);
  const SwaggerUIBundle = window.SwaggerUIBundle;
  if (typeof SwaggerUIBundle !== "function") {
    throw new Error("SwaggerUIBundle not loaded");
  }

  let specLoadUrl = specFileUrl;
  if (window.location.protocol === "file:") {
    specLoadUrl = URL.createObjectURL(new Blob([JSON.stringify(specRaw)], { type: "application/json" }));
    window.addEventListener("beforeunload", function () {
      URL.revokeObjectURL(specLoadUrl);
    });
  }

  const common = {
    dom_id: "#swagger-ui",
    deepLinking: true,
    displayRequestDuration: false,
    tryItOutEnabled: true,
    persistAuthorization: false,
    filter: true,
    requestInterceptor: validationRequestInterceptor(specForValidation, ajv, specLoadUrl),
    responseInterceptor: function (res) {
      if (pendingSyntheticResponses > 0) {
        pendingSyntheticResponses -= 1;
        return plainTextOkResponse();
      }
      const u = res.url || "";
      if (u.startsWith("data:application/json")) {
        return plainTextOkResponse();
      }
      return res;
    },
  };

  window.ui = SwaggerUIBundle(Object.assign({ url: specLoadUrl }, common));
}

mountOpenAPIExplorer().catch(function (err) {
  const el = document.getElementById("swagger-ui");
  if (el) {
    el.innerHTML =
      '<section class="card" role="alert"><h2>Could not start validator</h2><p>' +
      String(err && err.message ? err.message : err) +
      "</p></section>";
  }
});
