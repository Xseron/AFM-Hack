import { startRouter } from "./router.js";
import * as overview from "./views/overview.js";
import * as jobs from "./views/jobs.js";
import * as jobDetail from "./views/jobDetail.js";
import * as investigation from "./views/investigation.js";
import * as pipeline from "./views/pipeline.js";
import * as controls from "./views/controls.js";

const routes = [
  { match: /^\/overview$/, nav: "overview", module: overview },
  { match: /^\/jobs\/([^/]+)$/, nav: "jobs", module: jobDetail },
  { match: /^\/jobs$/, nav: "jobs", module: jobs },
  { match: /^\/investigation$/, nav: "investigation", module: investigation },
  { match: /^\/pipeline$/, nav: "pipeline", module: pipeline },
  { match: /^\/controls$/, nav: "controls", module: controls },
];

startRouter(routes, document.getElementById("view"));
