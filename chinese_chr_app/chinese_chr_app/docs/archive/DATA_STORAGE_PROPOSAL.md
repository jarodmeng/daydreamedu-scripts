# Data Storage & Logging Architecture Proposal

**Status: Superseded.** The app uses **Supabase (Postgres)** for character data, user data, and logging. This proposal’s recommended path (Hybrid → Firestore) was not adopted. Kept for historical context. Current storage: see [ARCHITECTURE.md](../ARCHITECTURE.md) and [backend/DATABASE.md](../../backend/DATABASE.md).

---

## Current State

- **Character Data**: JSON file (`characters.json`) - ~3000 characters, editable via frontend
- **Dictionary Data**: JSON file (`extracted_characters_hwxnet.json`) - read-only reference data
- **Logging**: File-based (`character_edits.log`) - JSON lines format
- **Images**: Google Cloud Storage (`chinese-chr-app-images` bucket)
- **Traffic**: ~20 requests/day (low volume)

## Future Requirements

- **User Authentication**: Login, profiles, preferences
- **User Data**: Per-user character favorites, progress, custom notes
- **Logging**: User actions, edits, analytics (will grow significantly with users)
- **Scalability**: Handle growth from 20/day to potentially thousands of users

---

## Option 1: Firestore (NoSQL) + Cloud Logging

### Architecture
- **User Data & Profiles**: Firestore collections (`users`, `user_profiles`, `user_favorites`)
- **Character Data**: Firestore collection (`characters`) - migrate from JSON
- **User Actions/Edits**: Firestore collection (`character_edits`) with timestamps
- **Application Logs**: Cloud Logging (structured JSON logs)
- **Analytics**: Firestore queries + optional BigQuery export

### Pros
✅ **Serverless & Auto-scaling**: No infrastructure management, scales automatically  
✅ **Real-time Updates**: Built-in real-time listeners (useful for collaborative features)  
✅ **Firebase Auth Integration**: Seamless user authentication (Google, email/password, etc.)  
✅ **Low Cost at Small Scale**: Free tier: 50K reads/day, 20K writes/day, 20K deletes/day  
✅ **JSON-like Structure**: Easy migration from current JSON files  
✅ **GCP Native**: Integrates well with Cloud Run, Cloud Storage  
✅ **Offline Support**: Can cache data client-side for offline use  
✅ **Flexible Schema**: Easy to add new fields without migrations  

### Cons
❌ **Query Limitations**: Complex queries can be expensive, limited join capabilities  
❌ **Cost at Scale**: Can get expensive with high read/write volumes  
❌ **No SQL Joins**: Need to denormalize data or make multiple queries  
❌ **Learning Curve**: Different from traditional SQL databases  

### Cost Estimate (Low Traffic)
- **Firestore**: Free tier covers ~20 requests/day easily
- **Cloud Logging**: Free tier: 50GB/month ingestion, 5GB/month storage
- **Total**: **$0/month** for current traffic, ~$5-10/month for 1000 active users

### Migration Effort
- **Medium**: Need to write migration script (JSON → Firestore)
- **Backend Changes**: Replace file I/O with Firestore SDK calls
- **Frontend Changes**: Add Firebase Auth, update API calls

---

## Option 2: Cloud SQL (PostgreSQL) + Cloud Logging

### Architecture
- **All Data**: PostgreSQL database (users, characters, edits, logs)
- **Application Logs**: Cloud Logging
- **Analytics**: SQL queries + optional BigQuery export

### Pros
✅ **SQL Familiarity**: Standard relational database, easy to query  
✅ **ACID Transactions**: Strong consistency guarantees  
✅ **Complex Queries**: JOINs, aggregations, analytics queries  
✅ **Mature Ecosystem**: Lots of libraries, tools, documentation  
✅ **Data Integrity**: Foreign keys, constraints, validation  
✅ **Backup/Restore**: Built-in automated backups  

### Cons
❌ **Infrastructure Management**: Need to manage database instance, scaling  
❌ **Higher Base Cost**: Minimum ~$7-15/month for smallest instance (even with no traffic)  
❌ **Connection Limits**: Need connection pooling for Cloud Run  
❌ **Scaling Complexity**: Manual scaling or read replicas for high traffic  
❌ **No Real-time**: Need to poll or use WebSockets for live updates  

### Cost Estimate
- **Cloud SQL (db-f1-micro)**: ~$7-10/month minimum
- **Cloud Logging**: Free tier
- **Total**: **~$7-10/month minimum**, scales with instance size

### Migration Effort
- **Medium-High**: Need to design schema, write migration scripts
- **Backend Changes**: Replace file I/O with SQLAlchemy/psycopg2
- **Frontend Changes**: Add auth (custom or Auth0), update API calls

---

## Option 3: Hybrid: Firestore (User Data) + GCS (Character Data) + Cloud Logging

### Architecture
- **User Data & Profiles**: Firestore (`users`, `user_profiles`, `user_favorites`)
- **Character Data**: Keep in GCS as JSON (read frequently, write rarely)
- **Character Edits**: Firestore collection (`character_edits`) - track who edited what
- **Application Logs**: Cloud Logging

### Pros
✅ **Best of Both Worlds**: Fast user queries (Firestore) + simple character storage (GCS)  
✅ **Lower Cost**: GCS is cheaper for large read-only datasets  
✅ **Easier Migration**: Keep character JSON in GCS, just add Firestore for users  
✅ **Separation of Concerns**: User data vs. reference data  

### Cons
❌ **Two Systems**: Need to manage both Firestore and GCS  
❌ **Character Edits Complexity**: Edits go to Firestore, but character data in GCS - need sync strategy  
❌ **Eventual Consistency**: If character data changes, need to update both places  

### Cost Estimate
- **Firestore**: Free tier for users
- **GCS**: ~$0.02/month (current)
- **Cloud Logging**: Free tier
- **Total**: **~$0-5/month** for low traffic

### Migration Effort
- **Low-Medium**: Move characters.json to GCS, add Firestore for users only
- **Backend Changes**: Read characters from GCS, write user data to Firestore
- **Frontend Changes**: Add Firebase Auth, update API calls

---

## Option 4: BigQuery (Analytics) + Firestore (Operational Data)

### Architecture
- **User Data & Characters**: Firestore (operational/real-time data)
- **Analytics & Logging**: BigQuery (historical data, analytics queries)
- **Application Logs**: Cloud Logging → BigQuery export

### Pros
✅ **Powerful Analytics**: BigQuery excels at large-scale analytics queries  
✅ **Cost-Effective Storage**: BigQuery storage is cheap (~$0.02/GB/month)  
✅ **Separation**: Operational data (Firestore) vs. analytical data (BigQuery)  
✅ **No ETL Needed**: Cloud Logging can export directly to BigQuery  

### Cons
❌ **Complexity**: Two systems to manage  
❌ **Overkill for Small Scale**: BigQuery is powerful but may be overkill initially  
❌ **Query Cost**: BigQuery charges per query (though free tier: 1TB/month)  

### Cost Estimate
- **Firestore**: Free tier
- **BigQuery**: Free tier (1TB queries/month, 10GB storage)
- **Total**: **$0/month** for small scale

### Migration Effort
- **High**: Need to set up data pipeline (Cloud Logging → BigQuery)
- **Backend Changes**: Firestore for operational data, export logs to BigQuery
- **Frontend Changes**: Add Firebase Auth

---

## Recommendation

### Phase 1 (Current → User Auth): **Option 3 (Hybrid)**

**Why:**
- **Lowest migration effort**: Keep character JSON in GCS (just move it there), add Firestore only for users
- **Lowest cost**: Free tier covers your current traffic
- **Fastest to implement**: Minimal changes to existing character data handling
- **Good foundation**: Easy to migrate characters to Firestore later if needed

**Implementation:**
1. Move `characters.json` to GCS (read from there in production)
2. Add Firestore for user data (`users`, `user_profiles`, `user_favorites`)
3. Add Firebase Authentication
4. Keep character edits in Firestore (`character_edits` collection)
5. Use Cloud Logging for application logs

### Phase 2 (Scale Up): **Option 1 (Full Firestore)**

**When to migrate:**
- When you have >1000 active users
- When character edits become frequent (multiple per day)
- When you need real-time collaboration features

**Why:**
- Better performance for frequent character edits
- Real-time updates for collaborative features
- Simpler architecture (one system instead of two)

### Phase 3 (Analytics): **Add BigQuery**

**When to add:**
- When you need complex analytics queries
- When you have >10GB of log data
- When you need historical trend analysis

---

## Detailed Comparison Table

| Feature | Firestore | Cloud SQL | Hybrid (GCS+Firestore) | BigQuery+Firestore |
|---------|-----------|-----------|------------------------|-------------------|
| **User Auth** | ✅ Firebase Auth | ⚠️ Custom/Auth0 | ✅ Firebase Auth | ✅ Firebase Auth |
| **Character Storage** | ✅ Good | ✅ Good | ✅ GCS (simple) | ✅ Firestore |
| **Query Flexibility** | ⚠️ Limited | ✅ Full SQL | ⚠️ Limited | ✅ Full SQL (analytics) |
| **Real-time Updates** | ✅ Built-in | ❌ No | ✅ Built-in | ❌ No |
| **Cost (Low Traffic)** | $0 | $7-10/mo | $0 | $0 |
| **Cost (High Traffic)** | $$ | $$ | $ | $$ |
| **Migration Effort** | Medium | Medium-High | Low-Medium | High |
| **Scalability** | ✅ Auto | ⚠️ Manual | ✅ Auto | ✅ Auto |
| **Learning Curve** | Medium | Low | Medium | High |

---

## Next Steps

1. **Decide on Phase 1 approach** (recommend Hybrid)
2. **Set up Firebase project** (if using Firestore)
3. **Migrate characters.json to GCS** (if using Hybrid)
4. **Implement Firebase Auth** in frontend
5. **Add Firestore collections** for user data
6. **Update backend** to read/write from new storage
7. **Test migration** with sample data

---

## Questions to Consider

1. **Do you need real-time collaboration?** (e.g., multiple users editing same character)
   - If yes → Firestore is better
   
2. **How complex will your analytics queries be?**
   - Simple aggregations → Firestore queries are fine
   - Complex JOINs/aggregations → Consider BigQuery later
   
3. **What's your user growth projection?**
   - Slow growth → Hybrid is fine
   - Fast growth → Plan for full Firestore migration

4. **Do you need offline support?**
   - If yes → Firestore has built-in offline support
