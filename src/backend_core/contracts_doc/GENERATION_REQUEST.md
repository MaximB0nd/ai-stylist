3. Generation Request (Frontend $\rightarrow$ Core Backend)

Accepts two source photographs along with transient metrics and questionnaire selections. 
Returns an asynchronous acceptance status (202 Accepted) since generation takes time.  

Method: POST

URL: /api/v1/generations

Headers:
- Authorization: Bearer <access_token>
- Content-Type: multipart/form-data

Form-Data Fields

- face_photo: binary file (close-up portrait, webp/jpeg/png)  
- body_photo: binary file (full-length body photo, webp/jpeg/png)  
- age: 26 (integer)  
- height: 172 (integer, in cm)  
- weight: 58 (integer, in kg)  
- situation: "office" (exact 1 value: "street", "study", "office", "evening")  
- styles: ["minimalism", "classic"] (1 to 2 values: "minimalism", "classic", "casual", "romantic")  
- shoes: ["loafers"] (1 to 2 values: "sneakers", "loafers", "heels", "boots")  
- impressions: ["confident", "elegant"] (1 to 2 values: "confident", "elegant", "relaxed", "bright")  

Responses

202 Accepted — Task queued successfully:  
```JSON{
  "generation_id": "c84dfb50-f331-4c12-88f5-3c1a3e6015aa",
  "status": "VALIDATING",
  "message": "Generation request accepted for processing",
  "status_poll_url": "/api/v1/generations/c84dfb50-f331-4c12-88f5-3c1a3e6015aa/status"
}
```

400 Bad Request — Missing required fields or invalid enum selection. 

422 Unprocessable Entity — Both mandatory images were not provided.


