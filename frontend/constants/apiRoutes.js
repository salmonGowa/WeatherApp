const LOCAL_URL = "http://127.0.0.1:8000/api/";

function normaliseBaseUrl(value) {
  const url = (value || "").trim();
  if (!url) return LOCAL_URL;
  return url.endsWith("/") ? url : `${url}/`;
}

const BASE_URL = normaliseBaseUrl(import.meta.env.VITE_API_URL);

const apiRoutes = {
  BASE_URL: BASE_URL,
  GEOCODE: "geocode/",
  PLAN: "plan/",
  HEATMAP: "heatmap/",
};

export default apiRoutes;
