// webpack.config.js
// This file configures how webpack should build our application

const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  // Entry point for the application - where webpack starts bundling
  entry: './src/index.tsx',
  
  // Output configuration - where and how webpack will output the bundled files
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    publicPath: '/',
  },
  
  // Enable source maps for debugging webpack's output
  devtool: 'source-map',
  
  // Configure how different file types should be processed
  module: {
    rules: [
      {
        // Process TypeScript files using ts-loader
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
      {
        // Process CSS files using style-loader and css-loader
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
      {
        // Process image files
        test: /\.(png|svg|jpg|jpeg|gif)$/i,
        type: 'asset/resource',
      },
    ],
  },
  
  // Configure file extensions that webpack should resolve
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
  },
  
  // Development server configuration
  devServer: {
    // Enable history API fallback for SPA routing
    historyApiFallback: true,
    // Set port for development server
    port: 3000,
    // Enable hot module replacement
    hot: true,
    // Configure proxy for API requests to avoid CORS issues
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        pathRewrite: { '^/api': '' },
      },
    },
  },
  
  // Configure plugins
  plugins: [
    // Generate an HTML file with the bundle script injected
    new HtmlWebpackPlugin({
      template: './src/index.html',
      filename: 'index.html',
    }),
  ],
};