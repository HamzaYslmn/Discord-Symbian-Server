module.exports = {
  apps: [
    {
      name: "gateway",
      script: "./src/index.ts",  // Path to your gateway's entry file
      watch: false,
      interpreter: "node",  // Ensure Node.js is used as the interpreter
      env: {
        NODE_ENV: "production",
        PORT: 8081
      }
    },
    {
      name: "http-proxy",
      script: "./proxy/index.js",  // Correct path to your proxy's entry file
      watch: false,
      interpreter: "node",  // Ensure Node.js is used as the interpreter
      env: {
        NODE_ENV: "production",
        PORT: 8080
      }
    }
  ]
};
