module.exports = {
    apps: [
      {
        name: "http-proxy",
        script: "./proxy/index.js",
        watch: false,
        env: {
          NODE_ENV: "production"
        },
        instances: 1,
        exec_mode: "fork",
        port: 8080
      },
      {
        name: "websocket-gateway",
        script: "./dist/index.js", // assuming your gateway app is built into the dist folder
        watch: false,
        env: {
          NODE_ENV: "production"
        },
        instances: 1,
        exec_mode: "fork",
        port: 8081
      }
    ]
  };
  