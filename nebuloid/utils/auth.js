import * as tools from '/utils_tools.js';

async function auth_init() {
  await tools.api_send("auth", { info: "request_data", data : "auth_params"});
}


async function authorize(username, password) {
  return await tools.api_send("auth", { info: "authorize", username: username, password: password });
}

async function signup(username, password) {
  return await tools.api_send("auth", { info: "signup", username: username, password: password });
}
async function logout() {
  const result = await tools.api_send("auth", { info: "logout" });
  return result.status === "success";
}
window.auth_init = auth_init;
window.authorize = authorize;
window.signup = signup;
window.logout = logout;
