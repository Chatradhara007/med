# AWS Backend Integration Guide (Phase 7)

This document describes the required AWS infrastructure to run CareThread in production or connected-development mode.

## 1. Authentication (Cognito)
Create an Amazon Cognito User Pool.
- Enable Hosted UI.
- Add an App Client.
- Set the callback URL to `http://localhost:5173` (or your production URL).
- Set the sign-out URL to `http://localhost:5173`.

## 2. API Gateway
Create a REST API Gateway.
- Configure a Cognito User Pool Authorizer for the API.
- Create endpoints:
  - `GET /record` (Authorized)
  - `POST /documents` (Authorized)
  - `GET /documents` (Authorized)
  - `GET /documents/{id}` (Authorized)
  - `PATCH /record/field` (Authorized)
  - `POST /substitution` (Authorized)
  - `GET /medicine/scans` (Authorized)
- Enable CORS for your frontend origin.

## 3. Data Storage (DynamoDB & S3)
- Create a DynamoDB table for Patient Records (Partition key: `patient_id`).
- Create an S3 bucket for Medical Documents.
- Configure S3 CORS to allow `PUT` and `GET` from the frontend origin for direct uploads.

## 4. Environment Configuration
Copy `.env.example` to `.env.local` in the `frontend` directory.
Set `VITE_USE_MOCK_API=false` and populate the AWS resource IDs.

The frontend is now designed to securely authenticate, retrieve the JWT token, and seamlessly append it as a `Bearer` token to all API Gateway requests.
