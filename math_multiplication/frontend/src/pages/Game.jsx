import { useState, useEffect, useRef } from 'react'
import '../App.css'

const API_URL = import.meta.env.VITE_API_URL || ''

function Game() {
  const [name, setName] = useState('')
  const [gameStarted, setGameStarted] = useState(false)
  const [gameCompleted, setGameCompleted] = useState(false)
  const [currentRound, setCurrentRound] = useState(1)
  const [questions, setQuestions] = useState([])
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [userAnswer, setUserAnswer] = useState('')
  const [showFeedback, setShowFeedback] = useState(null) // 'correct' or 'incorrect'
  const [startTime, setStartTime] = useState(null)
  const [elapsedTime, setElapsedTime] = useState(0) // in milliseconds
  const [gameLog, setGameLog] = useState([])
  const [results, setResults] = useState(null)
  const [totalQuestionsAnswered, setTotalQuestionsAnswered] = useState(0)
  
  const answerInputRef = useRef(null)
  const timerIntervalRef = useRef(null)
  const startTimeRef = useRef(null)
  const totalQuestionsAnsweredRef = useRef(0)
  const initialQuestionsRef = useRef([]) // Track the initial 20 unique questions
  const correctlyAnsweredQuestionsRef = useRef(new Set()) // Track which unique questions were answered correctly

  // Generate 20 unique random multiplication questions (2-12 x 2-12, excluding 1)
  const generateQuestions = () => {
    const newQuestions = []
    const questionSet = new Set() // Track unique questions (exact format: "num1×num2")
    
    while (newQuestions.length < 20) {
      // Generate numbers from 2 to 12 (excluding 1)
      const num1 = Math.floor(Math.random() * 11) + 2
      const num2 = Math.floor(Math.random() * 11) + 2
      // Create a unique key for the exact question format
      const questionKey = `${num1}×${num2}`
      
      // Only add if we haven't seen this exact question before
      // Note: "3×4" and "4×3" are considered different questions
      if (!questionSet.has(questionKey)) {
        questionSet.add(questionKey)
        newQuestions.push({
          num1,
          num2,
          correctAnswer: num1 * num2,
          answered: false,
          correct: null,
          userAnswer: null
        })
      }
    }
    return newQuestions
  }

  // Start the game
  const handleStartGame = (e) => {
    if (e) {
      e.preventDefault()
    }
    
    if (!name.trim()) {
      return
    }
    
    try {
      const initialQuestions = generateQuestions()
      if (!initialQuestions || initialQuestions.length !== 20) {
        console.error('Failed to generate questions')
        return
      }
      
      setQuestions(initialQuestions)
      const gameStartTime = Date.now()
      startTimeRef.current = gameStartTime
      setStartTime(gameStartTime)
      setCurrentQuestionIndex(0)
      setCurrentRound(1)
      setGameLog([])
      setElapsedTime(0)
      setGameCompleted(false)
      setResults(null)
      setTotalQuestionsAnswered(0)
      totalQuestionsAnsweredRef.current = 0
      // Store initial questions and reset tracking
      initialQuestionsRef.current = initialQuestions.map(q => `${q.num1}×${q.num2}`)
      correctlyAnsweredQuestionsRef.current = new Set()
      setGameStarted(true)
      
      // Start timer - update every 10ms for smooth display, but calculate from startTime for accuracy
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
      }
      timerIntervalRef.current = setInterval(() => {
        if (startTimeRef.current) {
          const now = Date.now()
          const elapsed = now - startTimeRef.current
          setElapsedTime(elapsed)
        }
      }, 10)
      
      // Focus input after a brief delay
      setTimeout(() => {
        if (answerInputRef.current) {
          answerInputRef.current.focus()
        }
      }, 100)
    } catch (error) {
      console.error('Error starting game:', error)
    }
  }

  // Format time as MM:SS (from milliseconds)
  const formatTime = (milliseconds) => {
    const totalSeconds = Math.floor(milliseconds / 1000)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  
  // Format time with milliseconds for display (MM:SS.mmm)
  const formatTimeWithMs = (milliseconds) => {
    const totalSeconds = Math.floor(milliseconds / 1000)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    const ms = milliseconds % 1000
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`
  }

  // Handle answer submission
  const handleSubmitAnswer = () => {
    if (!userAnswer.trim()) return
    
    const currentQuestion = questions[currentQuestionIndex]
    const answer = parseInt(userAnswer, 10)
    const isCorrect = answer === currentQuestion.correctAnswer
    
    // Update question
    const updatedQuestions = [...questions]
    const currentIdx = currentQuestionIndex // Capture current index
    updatedQuestions[currentIdx] = {
      ...currentQuestion,
      answered: true,
      correct: isCorrect,
      userAnswer: answer
    }
    setQuestions(updatedQuestions)
    
    // Log the question
    const logEntry = {
      round: currentRound,
      question: `${currentQuestion.num1} x ${currentQuestion.num2}`,
      correctAnswer: currentQuestion.correctAnswer,
      userAnswer: answer,
      isCorrect
    }
    setGameLog(prev => [...prev, logEntry])
    
    // Only count unique questions that are answered correctly for the first time
    const questionKey = `${currentQuestion.num1}×${currentQuestion.num2}`
    if (isCorrect && 
        initialQuestionsRef.current.includes(questionKey) && 
        !correctlyAnsweredQuestionsRef.current.has(questionKey)) {
      correctlyAnsweredQuestionsRef.current.add(questionKey)
      setTotalQuestionsAnswered(prev => prev + 1)
      totalQuestionsAnsweredRef.current += 1
    }
    
    // Show feedback
    setShowFeedback(isCorrect ? 'correct' : 'incorrect')
    
    // Clear input
    setUserAnswer('')
    
    // Hide feedback after 0.5s and move to next question
    setTimeout(() => {
      setShowFeedback(null)
      
      // Check if we've completed all questions in current round
      // Use captured index and updatedQuestions length to avoid closure issues
      if (currentIdx < updatedQuestions.length - 1) {
        setCurrentQuestionIndex(prev => prev + 1)
        // Focus input for next question
        setTimeout(() => {
          if (answerInputRef.current) {
            answerInputRef.current.focus()
          }
        }, 50)
      } else {
        // All questions in round completed
        checkRoundCompletion(updatedQuestions)
      }
    }, 500)
  }

  // Check if round is complete and handle next round or completion
  const checkRoundCompletion = (updatedQuestions) => {
    const wrongQuestions = updatedQuestions.filter(q => !q.correct)
    
    if (wrongQuestions.length === 0) {
      // All questions correct - game complete!
      completeGame()
    } else {
      // Start next round with wrong questions randomized
      const nextRoundQuestions = wrongQuestions.map(q => ({
        ...q,
        answered: false,
        correct: null,
        userAnswer: null
      }))
      
      // Shuffle the wrong questions
      for (let i = nextRoundQuestions.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [nextRoundQuestions[i], nextRoundQuestions[j]] = [nextRoundQuestions[j], nextRoundQuestions[i]]
      }
      
      setQuestions(nextRoundQuestions)
      setCurrentQuestionIndex(0)
      setCurrentRound(prev => prev + 1)
      
      // Focus input for next round
      setTimeout(() => {
        if (answerInputRef.current) {
          answerInputRef.current.focus()
        }
      }, 50)
    }
  }

  // Complete the game
  const completeGame = async () => {
    // Stop timer
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
    }
    
    // Calculate final time in milliseconds from startTime for accuracy
    const finalTime = startTimeRef.current ? Date.now() - startTimeRef.current : elapsedTime
    setElapsedTime(finalTime)
    
    // Use the set size as the definitive count of unique questions answered correctly
    // This ensures we only count the initial 20 unique questions, not reattempts
    const totalQuestions = correctlyAnsweredQuestionsRef.current.size
    
    setGameCompleted(true)
    setResults({
      name,
      time: finalTime,
      rounds: currentRound,
      totalQuestions
    })
    
    // Save game data to backend (time_elapsed in milliseconds)
    try {
      const response = await fetch(`${API_URL}/api/games`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          time_elapsed: finalTime, // in milliseconds
          rounds: currentRound,
          total_questions: totalQuestions
        })
      })
      
      if (!response.ok) {
        console.error('Failed to save game data')
      }
    } catch (error) {
      console.error('Error saving game data:', error)
    }
  }

  // Handle Enter key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && gameStarted && !gameCompleted) {
      handleSubmitAnswer()
    }
  }

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
      }
    }
  }, [])

  // Reset game
  const handleReset = () => {
    setName('')
    setGameStarted(false)
    setGameCompleted(false)
    setQuestions([])
    setCurrentQuestionIndex(0)
    setUserAnswer('')
    setShowFeedback(null)
    setStartTime(null)
    startTimeRef.current = null
    setElapsedTime(0)
    setCurrentRound(1)
    setGameLog([])
    setResults(null)
    setTotalQuestionsAnswered(0)
    totalQuestionsAnsweredRef.current = 0
    initialQuestionsRef.current = []
    correctlyAnsweredQuestionsRef.current = new Set()
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
  }

  const currentQuestion = questions[currentQuestionIndex]
  const totalQuestionsInRound = questions.length

  return (
    <div className="container">
      <div className="game-container">
        {!gameStarted ? (
          <div className="name-input-container">
            <h2>Enter Your First Name</h2>
            <input
              type="text"
              className="name-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && name.trim()) {
                  handleStartGame()
                }
              }}
              placeholder="Your name"
              autoFocus
            />
            <button
              type="button"
              className="start-button"
              onClick={handleStartGame}
              disabled={!name.trim()}
            >
              Start Game
            </button>
          </div>
        ) : gameCompleted ? (
          <div className="results-container">
            <h2>Game Complete!</h2>
            <div className="results-message">
              {results.name} answered {results.totalQuestions} questions correctly in {formatTime(results.time)} ({results.rounds} {results.rounds === 1 ? 'round' : 'rounds'})
            </div>
            <div className="results-stats">
              Time: {formatTimeWithMs(results.time)}
            </div>
            <button
              className="start-button"
              onClick={handleReset}
            >
              Play Again
            </button>
          </div>
        ) : (
          <>
            <div className="game-info">
              <div>
                Question {currentQuestionIndex + 1}/{totalQuestionsInRound} • Round {currentRound}
              </div>
              <div className="timer">
                {formatTime(elapsedTime)}
              </div>
            </div>
            
            <div className="question-container">
              <div className="question-display">
                {currentQuestion?.num1} × {currentQuestion?.num2}
              </div>
              <input
                ref={answerInputRef}
                type="number"
                className="answer-input"
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="?"
                autoFocus
              />
            </div>
          </>
        )}
        
        {showFeedback && (
          <div className={`feedback-overlay ${showFeedback === 'correct' ? 'feedback-correct' : 'feedback-incorrect'}`}>
            {showFeedback === 'correct' ? '✓' : '✗'}
          </div>
        )}
      </div>
    </div>
  )
}

export default Game
