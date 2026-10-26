import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Process, ProcessVersion, Execution, ExecutionStep } from '../models/process.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = 'http://localhost:8000/api/v1';

  constructor(private http: HttpClient) {}

  // Processes
  getProcesses(): Observable<Process[]> {
    return this.http.get<Process[]>(`${this.baseUrl}/processes`);
  }

  getProcess(id: string): Observable<Process> {
    return this.http.get<Process>(`${this.baseUrl}/processes/${id}`);
  }

  createProcess(name: string, description?: string): Observable<Process> {
    return this.http.post<Process>(`${this.baseUrl}/processes`, { name, description });
  }

  // Versions
  getVersions(processId: string): Observable<ProcessVersion[]> {
    return this.http.get<ProcessVersion[]>(`${this.baseUrl}/processes/${processId}/versions`);
  }

  createVersion(processId: string, definition: any): Observable<ProcessVersion> {
    return this.http.post<ProcessVersion>(
      `${this.baseUrl}/processes/${processId}/versions`,
      { definition }
    );
  }

  // Executions
  createExecution(processId: string, versionId: string, inputs?: any): Observable<Execution> {
    return this.http.post<Execution>(
      `${this.baseUrl}/processes/${processId}/executions`,
      { version_id: versionId, inputs }
    );
  }

  getExecutions(processId: string): Observable<Execution[]> {
    return this.http.get<Execution[]>(`${this.baseUrl}/processes/${processId}/executions`);
  }

  getExecution(executionId: string): Observable<Execution> {
    return this.http.get<Execution>(`${this.baseUrl}/executions/${executionId}`);
  }

  getExecutionSteps(executionId: string): Observable<ExecutionStep[]> {
    return this.http.get<ExecutionStep[]>(`${this.baseUrl}/executions/${executionId}/steps`);
  }

  // Recording
  startRecording(processId: string, targetUrl: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/recording/start`, { process_id: processId, target_url: targetUrl });
  }

  stopRecording(sessionId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/recording/${sessionId}/stop`, {});
  }

  getRecordingEvents(sessionId: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/recording/${sessionId}/events`);
  }
}
