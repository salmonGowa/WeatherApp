const LIVE_URL = import.meta.env.VITE_API_URL || "";
const LOCAL_URL = "http://127.0.0.1:8000/api/";
const BASE_URL = LIVE_URL || LOCAL_URL;

const apiRoutes = {
  BASE_URL: BASE_URL,
  GEOCODE: "geocode/",
  PLAN: "plan/",
  HEATMAP: "heatmap/",
};

export default apiRoutes;
