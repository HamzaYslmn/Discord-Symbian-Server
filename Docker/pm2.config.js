module.exports = {
  apps: [
    {
      name: "gateway",
      script: "./out/index.js",
      cwd: "./gateway",
      watch: false,
      env: {
        NODE_ENV: "production",
        PORT: 8081
      }
    },
    {
      name: "proxy",
      script: "./index.js",
      cwd: "./proxy",
      watch: false,
      env: {
        NODE_ENV: "production",
        PORT: 8080
      }
    }
  ]
};
